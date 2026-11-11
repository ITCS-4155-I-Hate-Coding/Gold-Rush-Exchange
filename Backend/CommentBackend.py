from db import query, transaction
import RepBackend as rep

# FIX: a length limit. Before, a comment could be any size.
COMMENT_MAX = 500


# how many levels of replies a thread can have (0 = the top-level comment itself).
# a reply to a comment that is already at the last level is placed beside it instead, so threads
# stay readable and can never grow endlessly deep
MAX_DEPTH = 4


def create_comment(user_id, post_id, content, parent_id=None):
    """Save a comment, or a reply to another comment when parent_id is given.
    Returns (ok, message, comment_id, post_author_id)."""
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

    depth = 0
    if parent_id is not None:
        # a reply must answer a comment that exists AND is on this same post
        parent = query(
            "SELECT id, post_id, parent_id, depth FROM comments WHERE id = %s",
            (parent_id,),
            fetchone=True,
        )
        if not parent or parent["post_id"] != post_id:
            return False, "That comment does not exist", None, None
        if parent["depth"] >= MAX_DEPTH:
            # already as deep as threads go: sit beside the comment being answered
            parent_id = parent["parent_id"]
            depth = parent["depth"]
        else:
            depth = parent["depth"] + 1

    row = query(
        "INSERT INTO comments (post_id, user_id, content, parent_id, depth) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (post_id, user_id, content, parent_id, depth),
        fetchone=True,
    )
    # the post's author is returned so the rep reward can skip comments on your own post
    return True, "Comment created successfully", row["id"], post["user_id"]


# like and dislike share one routine (same idea as _react in PostBackend.py):
# one transaction, a row lock, and a separate table + cached count column for each
REACTIONS = {
    "like": {"table": "comment_likes", "count": "likes", "opposite": "dislike"},
    "dislike": {"table": "comment_dislikes", "count": "dislikes", "opposite": "like"},
}


def _react(user_id, comment_id, kind):
    """Like or dislike (toggle). Clicking the same button again takes it back, and clicking the
    other one switches, so a user never has both on one comment. Returns (ok, message)."""
    mine = REACTIONS[kind]
    opposite = REACTIONS[mine["opposite"]]
    # (the table and column names come from the fixed dictionary above, never from the user)
    with transaction() as tx:
        comment = tx.query("SELECT id, user_id FROM comments WHERE id = %s FOR UPDATE", (comment_id,), fetchone=True)
        if not comment:
            return False, "Comment not found"

        # if this user already did this, clicking again removes it instead of stacking another
        removed = tx.query(
            f"DELETE FROM {mine['table']} WHERE user_id = %s AND comment_id = %s RETURNING 1",
            (user_id, comment_id),
            fetchone=True,
        )
        if removed:
            tx.query(f"UPDATE comments SET {mine['count']} = {mine['count']} - 1 WHERE id = %s", (comment_id,), fetch=False)
            return True, f"Comment un{kind}d"

        # switching: if they had the opposite reaction, take it off first
        switched = tx.query(
            f"DELETE FROM {opposite['table']} WHERE user_id = %s AND comment_id = %s RETURNING 1",
            (user_id, comment_id),
            fetchone=True,
        )
        if switched:
            tx.query(
                f"UPDATE comments SET {opposite['count']} = {opposite['count']} - 1 WHERE id = %s",
                (comment_id,),
                fetch=False,
            )

        tx.query(f"INSERT INTO {mine['table']} (user_id, comment_id) VALUES (%s, %s)", (user_id, comment_id), fetch=False)
        tx.query(f"UPDATE comments SET {mine['count']} = {mine['count']} + 1 WHERE id = %s", (comment_id,), fetch=False)
        if kind == "like":
            # REP: +1 to the comment's author (not for self-likes; once per person per comment)
            # dislikes never change anyone's rep
            rep.reward_like(comment["user_id"], user_id, "comment", comment_id, tx=tx)
        return True, f"Comment {kind}d"


def like_comment(user_id, comment_id):
    return _react(user_id, comment_id, "like")


def dislike_comment(user_id, comment_id):
    return _react(user_id, comment_id, "dislike")


def view_comments(post_id, user_id = None):
    return view_comments_for_posts([post_id], user_id)


def view_comments_for_posts(post_id, user_id=None):
    # every comment on a list of posts in one query so the posts tab doesnt ask once per post
    # 
    return query(
        """
        SELECT comments.id, comments.post_id, comments.parent_id, comments.depth, comments.content, comments.likes, comments.dislikes,
               comments.created_at, users.username,
               EXISTS(SELECT 1 FROM comment_likes cl WHERE cl.comment_id = comments.id AND cl.user_id = %s) AS liked_by_me,
               EXISTS(SELECT 1 FROM comment_dislikes cd WHERE cd.comment_id = comments.id AND cd.user_id = %s) AS disliked_by_me
        FROM comments
        JOIN users ON users.id = comments.user_id
        WHERE comments.post_id = ANY(%s)
        ORDER BY comments.created_at ASC, comments.id ASC
        """,
        (user_id, user_id, list(post_id)),
    )