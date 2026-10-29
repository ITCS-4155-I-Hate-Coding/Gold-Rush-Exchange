from db import query, transaction
import RepBackend as rep

# FIX: a length limit. Before, a comment could be any size.
COMMENT_MAX = 500


def create_comment(user_id, post_id, content):
    """Save a comment. Returns (ok, message, comment_id, post_author_id)."""
    # reject any empty comments
    content = (content or "").strip()
    if not content:
        return False, "Comment content is required", None, None
    if len(content) > COMMENT_MAX:
        return False, f"Comments can be at most {COMMENT_MAX} characters.", None, None

    # confirm the post actually exists before attaching a comment to it
    post = query("SELECT id, user_id FROM posts WHERE id = %s", (post_id,), fetchone=True)
    if not post:
        return False, "That post does not exist", None, None

    row = query(
        "INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s) RETURNING id",
        (post_id, user_id, content),
        fetchone=True,
    )
    # the post's author is returned so the rep reward can skip comments on your own post
    return True, "Comment created successfully", row["id"], post["user_id"]


# similar to like_post in PostBackend.py (one transaction, row lock, rep for the author)
def like_comment(user_id, comment_id):
    with transaction() as tx:
        comment = tx.query("SELECT id, user_id FROM comments WHERE id = %s FOR UPDATE", (comment_id,), fetchone=True)
        if not comment:
            return False, "Comment not found"

        # if this user already liked the comment, clicking again removes the like instead of stacking another
        removed = tx.query(
            "DELETE FROM comment_likes WHERE user_id = %s AND comment_id = %s RETURNING 1",
            (user_id, comment_id),
            fetchone=True,
        )
        if removed:
            tx.query("UPDATE comments SET likes = likes - 1 WHERE id = %s", (comment_id,), fetch=False)
            return True, "Comment unliked"

        tx.query("INSERT INTO comment_likes (user_id, comment_id) VALUES (%s, %s)", (user_id, comment_id), fetch=False)
        tx.query("UPDATE comments SET likes = likes + 1 WHERE id = %s", (comment_id,), fetch=False)
        # REP: +1 to the comment's author (not for self-likes; once per person per comment)
        rep.reward_like(comment["user_id"], user_id, "comment", comment_id, tx=tx)
        return True, "Comment liked"


def view_comments(post_id, user_id=None):
    # using JOIN to pull username with comment to see who said what, plus whether the current user has liked it
    return query(
        """
        SELECT comments.id, comments.content, comments.likes, comments.created_at, users.username,
               EXISTS(SELECT 1 FROM comment_likes cl WHERE cl.comment_id = comments.id AND cl.user_id = %s) AS liked_by_me
        FROM comments
        JOIN users ON users.id = comments.user_id WHERE comments.post_id = %s ORDER BY comments.created_at ASC
        """,
        (user_id, post_id),
    )