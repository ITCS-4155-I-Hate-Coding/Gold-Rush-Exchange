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
def like_comment(comment_id):
    result = query(
        "UPDATE comments SET likes = likes + 1 WHERE id = %s RETURNING id",
        (comment_id,),
        fetchone=True
    )
    if not result:
        return False, "Comment not found"
    return True, "Comment liked"


def view_comments(post_id):
    # using JOIN to pull username with comment to see who said what
    return query(
        """
        SELECT comments.id, comments.content, comments.likes, comments.created_at, users.username FROM comments
        JOIN users ON users.id = comments.user_id WHERE comments.post_id = %s ORDER BY comments.created_at ASC
        """,
        (post_id,),

    )
    



  

# testing for now
if __name__ == "__main__":
    print("Gold-Rush-Exchange Comment System")
    print("---------------------------------")

    
