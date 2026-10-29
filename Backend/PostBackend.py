import json
from pathlib import Path
from db import query, transaction
import RepBackend as rep



# FIX: a length limit. Before, a post could be any size.
POST_MAX = 1000

# FIX: the feed returns the newest posts only, instead of every post ever written
FEED_POSTS = 100


def create_post(user_id, content):
    """Save a post. Returns (ok, message, post_id)."""
    content = (content or "").strip()
    if not content:
        return False, "Post content is required.", None
    if len(content) > POST_MAX:
        return False, f"Posts can be at most {POST_MAX} characters.", None
    row = query(
        "INSERT INTO posts (user_id, content) VALUES (%s, %s) RETURNING id",
        (user_id, content),
        fetchone=True,
    )
    return True, "Post created successfully.", row["id"]


def like_post(user_id, post_id):
    """Like or unlike (toggle). Returns (ok, message)."""
    # FIX: one transaction. Before, the like row and the cached like count were changed by two
    # separate commits, so a crash or two fast clicks could leave the count wrong.
    with transaction() as tx:
        # FOR UPDATE locks this post's row until the transaction ends, so two likes on the same
        # post at the same moment are applied one after the other
        post = tx.query("SELECT id, user_id FROM posts WHERE id = %s FOR UPDATE", (post_id,), fetchone=True)
        if not post:
            return False, "Post not found."

        # if this user already liked the post, clicking again removes the like instead of stacking another
        removed = tx.query(
            "DELETE FROM post_likes WHERE user_id = %s AND post_id = %s RETURNING 1",
            (user_id, post_id),
            fetchone=True,
        )
        if removed:
            tx.query("UPDATE posts SET likes = likes - 1 WHERE id = %s", (post_id,), fetch=False)
            return True, "Post unliked"

        tx.query("INSERT INTO post_likes (user_id, post_id) VALUES (%s, %s)", (user_id, post_id), fetch=False)
        tx.query("UPDATE posts SET likes = likes + 1 WHERE id = %s", (post_id,), fetch=False)
        # REP: +1 to the author (not for self-likes; only once per person per post, ever)
        rep.reward_like(post["user_id"], user_id, "post", post_id, tx=tx)
        return True, "Post liked"


def view_posts(user_id=None, limit=FEED_POSTS):
    # using join to group together the post with the username, plus whether the current user has liked it
    return query(
        """
        SELECT posts.id, posts.content, posts.likes, posts.created_at, users.username,
               EXISTS(SELECT 1 FROM post_likes pl WHERE pl.post_id = posts.id AND pl.user_id = %s) AS liked_by_me
        FROM posts JOIN users ON users.id = posts.user_id
        ORDER BY posts.created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
