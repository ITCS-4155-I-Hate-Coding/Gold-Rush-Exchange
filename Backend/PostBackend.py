import json
from pathlib import Path
from db import query, transaction
import RepBackend as rep
import ImageBackend as images



# FIX: a length limit. Before, a post could be any size.
POST_MAX = 1000

# FIX: the feed returns the newest posts only, instead of every post ever written
FEED_POSTS = 100


def create_post(user_id, content, image=None):
    """Save a post, with an optional picture (an uploaded file). Returns (ok, message, post_id)."""
    content = (content or "").strip()
    # a post needs words or a picture (or both)
    if not content and not image:
        return False, "Post content is required.", None
    if len(content) > POST_MAX:
        return False, f"Posts can be at most {POST_MAX} characters.", None

    filename = None
    if image:
        filename, error = images.save_image(image)
        if error:
            return False, error, None
    try:
        row = query(
            "INSERT INTO posts (user_id, content, image_filename) VALUES (%s, %s, %s) RETURNING id",
            (user_id, content, filename),
            fetchone=True,
        )
    except Exception:
        images.delete_image(filename)  # don't leave a picture behind that no post points to
        raise
    return True, "Post created successfully.", row["id"]


# like and dislike work the same way, so they share one routine below.
# each has its own table of who did it, and its own cached count column on posts
REACTIONS = {
    "like": {"table": "post_likes", "count": "likes", "opposite": "dislike"},
    "dislike": {"table": "post_dislikes", "count": "dislikes", "opposite": "like"},
}


def _react(user_id, post_id, kind):
    """Like or dislike (toggle). Clicking the same button again takes it back, and clicking the
    other one switches, so a user never has both on one post. Returns (ok, message)."""
    mine = REACTIONS[kind]
    opposite = REACTIONS[mine["opposite"]]
    # (the table and column names come from the fixed dictionary above, never from the user)

    # FIX: one transaction. Before, the like row and the cached like count were changed by two
    # separate commits, so a crash or two fast clicks could leave the count wrong.
    with transaction() as tx:
        # FOR UPDATE locks this post's row until the transaction ends, so two clicks on the same
        # post at the same moment are applied one after the other
        post = tx.query("SELECT id, user_id FROM posts WHERE id = %s FOR UPDATE", (post_id,), fetchone=True)
        if not post:
            return False, "Post not found."

        # if this user already did this, clicking again removes it instead of stacking another
        removed = tx.query(
            f"DELETE FROM {mine['table']} WHERE user_id = %s AND post_id = %s RETURNING 1",
            (user_id, post_id),
            fetchone=True,
        )
        if removed:
            tx.query(f"UPDATE posts SET {mine['count']} = {mine['count']} - 1 WHERE id = %s", (post_id,), fetch=False)
            return True, f"Post un{kind}d"

        # switching: if they had the opposite reaction, take it off first
        switched = tx.query(
            f"DELETE FROM {opposite['table']} WHERE user_id = %s AND post_id = %s RETURNING 1",
            (user_id, post_id),
            fetchone=True,
        )
        if switched:
            tx.query(
                f"UPDATE posts SET {opposite['count']} = {opposite['count']} - 1 WHERE id = %s",
                (post_id,),
                fetch=False,
            )

        tx.query(f"INSERT INTO {mine['table']} (user_id, post_id) VALUES (%s, %s)", (user_id, post_id), fetch=False)
        tx.query(f"UPDATE posts SET {mine['count']} = {mine['count']} + 1 WHERE id = %s", (post_id,), fetch=False)
        if kind == "like":
            # REP: +1 to the author (not for self-likes; only once per person per post, ever)
            # dislikes never change anyone's rep
            rep.reward_like(post["user_id"], user_id, "post", post_id, tx=tx)
        return True, f"Post {kind}d"


def like_post(user_id, post_id):
    return _react(user_id, post_id, "like")


def dislike_post(user_id, post_id):
    return _react(user_id, post_id, "dislike")


def view_posts(user_id=None, limit=FEED_POSTS):
    # using join to group together the post with the username, plus whether the current user has liked
    # or disliked it
    rows = query(
        """
        SELECT posts.id, posts.content, posts.likes, posts.dislikes, posts.image_filename, posts.created_at,
               users.username,
               EXISTS(SELECT 1 FROM post_likes pl WHERE pl.post_id = posts.id AND pl.user_id = %s) AS liked_by_me,
               EXISTS(SELECT 1 FROM post_dislikes pd WHERE pd.post_id = posts.id AND pd.user_id = %s) AS disliked_by_me
        FROM posts JOIN users ON users.id = posts.user_id
        ORDER BY posts.created_at DESC
        LIMIT %s
        """,
        (user_id, user_id, limit),
    )
    # the page gets a ready-to-use address for the picture, not the file name
    for row in rows:
        row["image_url"] = images.url_for(row.pop("image_filename"))
    return rows