import json
from pathlib import Path
from db import query


def create_comment(user_id, post_id, content):
    # reject any empty comments
    if not content:
        return False, "Comment content is required"

    # confirm the post actually exists before attaching a comment to it
    post = query(
        "SELECT id FROM posts WHERE id = %s",
        (post_id, ),
        fetchone=True
    )
    if not post:
        return False, "That post does not exist"

    query(
        "INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)",
        (post_id, user_id, content),
        fetch=False
    )

    return True, "Comment created successfully"


# similar to like_post in PostBackend.py
def like_comment(user_id, comment_id):
    comment = query("SELECT id FROM comments WHERE id = %s", (comment_id,), fetchone=True)
    if not comment:
        return False, "Comment not found"

    # if this user already liked the comment, clicking again removes the like instead of stacking another
    existing = query(
        "SELECT 1 FROM comment_likes WHERE user_id = %s AND comment_id = %s",
        (user_id, comment_id),
        fetchone=True
    )

    if existing:
        query("DELETE FROM comment_likes WHERE user_id = %s AND comment_id = %s", (user_id, comment_id), fetch=False)
        query("UPDATE comments SET likes = likes - 1 WHERE id = %s", (comment_id,), fetch=False)
        return True, "Comment unliked"

    query("INSERT INTO comment_likes (user_id, comment_id) VALUES (%s, %s)", (user_id, comment_id), fetch=False)
    query("UPDATE comments SET likes = likes + 1 WHERE id = %s", (comment_id,), fetch=False)
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
    



  

# testing for now
if __name__ == "__main__":
    print("Gold-Rush-Exchange Comment System")
    print("---------------------------------")

    
