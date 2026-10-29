"""
Private messages between friends

Friends are two users that follow each other while following is just one sided that way it doesnt have that stranger feel to it

1. only friends can send messages to each other
2. even if someone unfollows, the conversation will still be readable but you cannot send messages until you are friends again
3. messages can be between 1-1000 characters
4. opening someones message marks it as read

"""

from db import query

MESSAGE_MAX = 1000
RATE_LIMIT = 20       # messages...
RATE_WINDOW = 60      # ...per this many seconds
PAGE_SIZE = 50        # messages loaded at a time when a conversation opens


def _user_id(username):
    row = query("SELECT id, username FROM users WHERE username = %s", (username,), fetchone=True)
    return row


def are_friends(a_id, b_id):
    """True if a follows b AND b follows a."""
    row = query(
        """
        SELECT EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s)
           AND EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s) AS ok
        """,
        (a_id, b_id, b_id, a_id),
        fetchone=True,
    )
    return bool(row and row["ok"])


def list_conversations(user_id):
    """The left-hand list on the Messages tab: every friend, plus anyone you have messages with,
    each with the last message and how many unread messages they've sent you.
    Ordered by most recent message (friends you haven't talked to yet come last, A-Z)."""
    return query(
        """
        WITH friends AS (
            SELECT f1.followed_id AS other_id
            FROM follows f1
            JOIN follows f2 ON f2.follower_id = f1.followed_id AND f2.followed_id = f1.follower_id
            WHERE f1.follower_id = %(me)s
        ),
        partners AS (
            -- anyone with message history, even if no longer friends
            SELECT CASE WHEN sender_id = %(me)s THEN recipient_id ELSE sender_id END AS other_id
            FROM messages WHERE sender_id = %(me)s OR recipient_id = %(me)s
            UNION
            SELECT other_id FROM friends
        )
        SELECT u.username, u.reputation,
               (u.id IN (SELECT other_id FROM friends)) AS is_friend,
               last.body AS last_body, last.created_at AS last_at, (last.sender_id = %(me)s) AS last_from_me,
               (SELECT COUNT(*) FROM messages m
                 WHERE m.sender_id = u.id AND m.recipient_id = %(me)s AND m.read_at IS NULL)::int AS unread
        FROM partners p
        JOIN users u ON u.id = p.other_id
        LEFT JOIN LATERAL (
            SELECT body, created_at, sender_id FROM messages m
            WHERE (m.sender_id = %(me)s AND m.recipient_id = u.id) OR (m.sender_id = u.id AND m.recipient_id = %(me)s)
            ORDER BY m.id DESC LIMIT 1
        ) last ON true
        ORDER BY last.created_at DESC NULLS LAST, lower(u.username)
        """,
        {"me": user_id},
    )


def get_conversation(user_id, other_username, after_id=None, before_id=None, limit=PAGE_SIZE):
    """Messages between the user and someone else, oldest first.

    after_id:  only messages newer than this id (what the page polls for)
    before_id: only messages older than this id ("load earlier messages")
    neither:   the newest `limit` messages
    Also marks the other person's messages to you as read.
    Returns (data, error).
    """
    other = _user_id(other_username)
    if not other:
        return None, "User not found."
    if other["id"] == user_id:
        return None, "You can't message yourself."

    friends = are_friends(user_id, other["id"])
    pair = "((m.sender_id = %(me)s AND m.recipient_id = %(other)s) OR (m.sender_id = %(other)s AND m.recipient_id = %(me)s))"
    params = {"me": user_id, "other": other["id"], "limit": limit, "after": after_id, "before": before_id}
    if after_id is not None:
        rows = query(f"SELECT m.* FROM messages m WHERE {pair} AND m.id > %(after)s ORDER BY m.id LIMIT 200", params)
    else:
        extra = "AND m.id < %(before)s" if before_id is not None else ""
        rows = query(
            f"SELECT * FROM (SELECT m.* FROM messages m WHERE {pair} {extra} ORDER BY m.id DESC LIMIT %(limit)s) x ORDER BY id",
            params,
        )
    if not rows and not friends and after_id is None and before_id is None:
        return None, "You can only message friends (people who follow you back)."

    # opening the conversation counts as reading it
    query(
        "UPDATE messages SET read_at = now() WHERE sender_id = %s AND recipient_id = %s AND read_at IS NULL",
        (other["id"], user_id),
        fetch=False,
    )
    return {
        "with": other["username"],
        "can_send": friends,
        "messages": [
            {"id": r["id"], "body": r["body"], "created_at": r["created_at"],
             "from_me": r["sender_id"] == user_id, "read": r["read_at"] is not None}
            for r in rows
        ],
        # True when there may be older messages to load
        "has_more": after_id is None and len(rows) == limit,
    }, None


def send_message(user_id, other_username, body):
    """Send a message. Returns (ok, message, saved_message_or_None)."""
    body = (body or "").strip()
    if not body:
        return False, "Write a message first.", None
    if len(body) > MESSAGE_MAX:
        return False, f"Messages can be at most {MESSAGE_MAX} characters.", None

    other = _user_id(other_username)
    if not other:
        return False, "User not found.", None
    if other["id"] == user_id:
        return False, "You can't message yourself.", None
    if not are_friends(user_id, other["id"]):
        return False, "You can only message friends (people who follow you back).", None

    # one statement: insert only if the sender is under the rate limit
    row = query(
        """
        INSERT INTO messages (sender_id, recipient_id, body)
        SELECT %(me)s, %(other)s, %(body)s
        WHERE (SELECT COUNT(*) FROM messages WHERE sender_id = %(me)s
               AND created_at > now() - make_interval(secs => %(window)s)) < %(limit)s
        RETURNING id, body, created_at
        """,
        {"me": user_id, "other": other["id"], "body": body, "window": RATE_WINDOW, "limit": RATE_LIMIT},
        fetchone=True,
    )
    if not row:
        return False, "You're sending messages too quickly. Wait a moment and try again.", None
    return True, "Sent", {"id": row["id"], "body": row["body"], "created_at": row["created_at"],
                          "from_me": True, "read": False}