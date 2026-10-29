"""
The bell in the header

For now what will be creating notifications:

    - achievement progress: "75% of the way to..."
    - achievement unlocked

These notifications wont be created twice because of the keys

This page will also get a summary every 20-30 seconds quickly in order to keep the progress up to date
"""

import json

from db import query

LIST_LIMIT = 30  # how many notifications the bell panel shows


def create_many(user_id, items):
    """Insert several notifications in one statement, skipping any whose dedupe_key already exists.

    items: list of dicts with kind, title, body and optionally link, code, key (the dedupe_key).
    Returns how many were actually created.
    """
    if not items:
        return 0
    rows = query(
        """
        INSERT INTO notifications (user_id, kind, title, body, link, code, dedupe_key)
        SELECT %s, x.kind, x.title, x.body, x.link, x.code, x.key
        FROM json_to_recordset(%s::json) AS x(kind text, title text, body text, link text, code text, key text)
        ON CONFLICT (user_id, dedupe_key) DO NOTHING
        RETURNING id
        """,
        (user_id, json.dumps(items)),
    )
    return len(rows)


def list_notifications(user_id, limit=LIST_LIMIT):
    """Newest notifications first, plus how many are unread."""
    rows = query(
        "SELECT id, kind, title, body, link, code, created_at, read_at IS NOT NULL AS read "
        "FROM notifications WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
        (user_id, limit),
    )
    return {"notifications": rows, "unread": summary(user_id)["unread_notifications"]}


def mark_read(user_id, ids=None):
    """Mark the given notification ids as read, or all of them when ids is None.
    Only the user's own notifications can be changed (the WHERE includes user_id)."""
    if ids is None:
        query("UPDATE notifications SET read_at = now() WHERE user_id = %s AND read_at IS NULL",
              (user_id,), fetch=False)
        return True, "All notifications marked as read."
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return False, "Send a list of notification ids."
    query("UPDATE notifications SET read_at = now() WHERE user_id = %s AND id = ANY(%s) AND read_at IS NULL",
          (user_id, ids), fetch=False)
    return True, "Marked as read."


def summary(user_id):
    """The two numbers the header shows: unread notifications (bell) and unread messages (Messages tab)."""
    return query(
        """
        SELECT
            (SELECT COUNT(*) FROM notifications WHERE user_id = %s AND read_at IS NULL)::int AS unread_notifications,
            (SELECT COUNT(*) FROM messages WHERE recipient_id = %s AND read_at IS NULL)::int AS unread_messages
        """,
        (user_id, user_id),
        fetchone=True,
    )