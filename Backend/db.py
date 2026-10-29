"""

"""

import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

import threading
import time
from contextlib import contextmanager

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jacobware@localhost:5432/goldrushexchange" # real url is in the .env folder for privacy
)


# pool size: at least 1 connection kept open, at most 10 in use at the same time
POOL_MIN = 1
POOL_MAX = 10

# a connection that has sat unused for longer than this is tested before it's handed out,
# because hosted databases (Neon) close idle connections after a few minutes
IDLE_CHECK_SECONDS = 60

_pool = None
_pool_lock = threading.Lock()
_last_used = {}  # id(connection) -> time it was last returned to the pool


def _get_pool():
    # the pool is created on first use (not at import) so the app can still start if the
    # database is briefly unreachable; the first query will simply try again
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    POOL_MIN, POOL_MAX, DATABASE_URL,
                    # keepalives stop network equipment from silently dropping idle connections
                    keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
                )
    return _pool


def _checkout():
    """Borrow a working connection from the pool."""
    pool = _get_pool()
    for _ in range(3):
        conn = pool.getconn()
        idle = time.time() - _last_used.get(id(conn), 0)
        if conn.closed:
            pool.putconn(conn, close=True)
            continue
        if idle > IDLE_CHECK_SECONDS:
            # quick health check; a connection the server already closed fails here instead of
            # in the middle of a real query
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
            except psycopg2.Error:
                pool.putconn(conn, close=True)
                continue
        return conn
    # three bad connections in a row: let the error surface on a fresh attempt
    return pool.getconn()


def _checkin(conn):
    """Give a connection back to the pool."""
    _last_used[id(conn)] = time.time()
    _get_pool().putconn(conn, close=bool(conn.closed))


def get_connection():
    # kept for backwards compatibility with older scripts; new code should use query()/transaction()
    return psycopg2.connect(DATABASE_URL)


class _Tx:
    """What transaction() hands you: the same query() signature, but nothing is committed until
    the with-block finishes without an error."""

    def __init__(self, cur):
        self._cur = cur

    def query(self, sql, params=None, fetch=True, fetchone=False):
        self._cur.execute(sql, params or ())
        if not fetch:
            return None
        return self._cur.fetchone() if fetchone else self._cur.fetchall()


@contextmanager
def transaction():
    """Run several statements as one unit: all are saved together, or (on any error) none are."""
    conn = _checkout()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield _Tx(cur)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        _checkin(conn)


def query(sql, params=None, fetch=True, fetchone=False):
    """
    Query Note:
    fetch=True, fetchone=False -> returns a list of dict-like rows
    fetch=True, fetchone=True  -> returns single dict-like row (or None)
    fetch=False                -> returns None (use for INSERT/UPDATE/DELETE)
    Values always go in params (never pasted into the SQL text), which prevents SQL injection.
    """
    with transaction() as tx:
        return tx.query(sql, params, fetch=fetch, fetchone=fetchone)












# def get_connection():
#     return psycopg2.connect(DATABASE_URL)

# def query(sql, params=None, fetch=True, fetchone=False):
#     """
#     Query Note:
#     fetch=True, fetchone=False -> returns a list of dict-like rows
#     fetch=True, fetchone=True  -> returns single dict-like row
#     fetch=False                -> returns None (use for INSERT/UPDATE/DELETE)
#     """
#     getConn = get_connection()
#     try:
#         with getConn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             cur.execute(sql, params or ())
#             if fetch:
#                 result = cur.fetchone() if fetchone else cur.fetchall()
#             else:
#                 result=None
#             getConn.commit()
#             return result
#     finally:
#         getConn.close()