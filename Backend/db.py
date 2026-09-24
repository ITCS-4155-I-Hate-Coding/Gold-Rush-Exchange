"""

"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://jacobware@localhost:5432/goldrushexchange" # real url is in the .env folder for privacy
)

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def query(sql, params=None, fetch=True, fetchone=False):
    """
    Query Note:
    fetch=True, fetchone=False -> returns a list of dict-like rows
    fetch=True, fetchone=True  -> returns single dict-like row
    fetch=False                -> returns None (use for INSERT/UPDATE/DELETE)
    """
    getConn = get_connection()
    try:
        with getConn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch:
                result = cur.fetchone() if fetchone else cur.fetchall()
            else:
                result=None
            getConn.commit()
            return result
    finally:
        getConn.close()