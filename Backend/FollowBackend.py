from db import query

# how many items to show in the "people you follow" activity feed
FEED_LIMIT = 50


def follow_user(follower_id, username):
    target = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
    if not target:
        return False, "User not found."
    if target["id"] == follower_id:
        return False, "You can't follow yourself."

    # ON CONFLICT DO NOTHING means following someone twice is harmless
    query(
        "INSERT INTO follows (follower_id, followed_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (follower_id, target["id"]),
        fetch=False,
    )
    return True, f"You are now following {username}."


def unfollow_user(follower_id, username):
    target = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
    if not target:
        return False, "User not found."

    query(
        "DELETE FROM follows WHERE follower_id = %s AND followed_id = %s",
        (follower_id, target["id"]),
        fetch=False,
    )
    return True, f"You unfollowed {username}."


def get_following(user_id):
    # everyone this user follows, most recently followed first
    return query(
        """
        SELECT users.username, users.reputation, follows.created_at AS followed_at
        FROM follows
        JOIN users ON users.id = follows.followed_id
        WHERE follows.follower_id = %s
        ORDER BY follows.created_at DESC
        """,
        (user_id,),
    )


def get_following_feed(user_id, limit=FEED_LIMIT):
    # posts and predictions from the people this user follows, newest first
    return query(
        """
        SELECT type, username, title, body, result, points, created_at FROM (
            SELECT 'post' AS type, u.username, NULL::text AS title,
                   CASE WHEN p.content = '' THEN '(photo)' ELSE p.content END AS body,
                   NULL::text AS result, NULL::int AS points, p.created_at
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.user_id IN (SELECT followed_id FROM follows WHERE follower_id = %s)
            UNION ALL
            SELECT 'prediction', u.username, pr.game, pr.prediction_text,
                   pr.result, pr.points, pr.created_at
            FROM predictions pr
            JOIN users u ON u.id = pr.user_id
            WHERE pr.user_id IN (SELECT followed_id FROM follows WHERE follower_id = %s)
                ) AS feed
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, user_id, limit),
    )

    

def search_users(user_id, text, limit=10):
    text = (text or "").strip()
    if not text:
        return []

    # escape LIKE wildcards so typing % or _ searches for those characters literally
    safe = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # usernames that contain the text (not you), names that START with it first,
    # plus whether you already follow each one
    return query(
        """
        SELECT u.username, u.reputation,
               EXISTS(SELECT 1 FROM follows f
                      WHERE f.follower_id = %s AND f.followed_id = u.id) AS is_following
        FROM users u
        WHERE u.id <> %s AND u.username ILIKE %s
        ORDER BY (u.username ILIKE %s) DESC, u.username
        LIMIT %s
        """,
        (user_id, user_id, "%" + safe + "%", safe + "%", limit),
        
    )



def get_followers(user_id):
    # everyone who follows this user, newest follower first,
    # plus whether this user already follows them back
    return query(
        """
        SELECT u.username, u.reputation, f.created_at AS followed_at,
               EXISTS(SELECT 1 FROM follows b
                      WHERE b.follower_id = %s AND b.followed_id = u.id) AS is_following
        FROM follows f
        JOIN users u ON u.id = f.follower_id
        WHERE f.followed_id = %s
        ORDER BY f.created_at DESC
        """,
        (user_id, user_id),
    )