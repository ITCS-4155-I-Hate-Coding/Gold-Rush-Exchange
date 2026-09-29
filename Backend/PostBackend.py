import json
from pathlib import Path
from db import query



def create_post(user_id, content):
    if not content:
        return False, "Post content is required."
    query(
        "INSERT INTO posts (user_id, content) VALUES (%s, %s)",
        (user_id, content),
        fetch=False

    )
    return True, "Post created successfully."
    


def like_post(user_id, post_id):
    post = query("SELECT id FROM posts WHERE id = %s", (post_id,), fetchone=True)
    if not post:
        return False, "Post not found."

    # if this user already liked the post, clicking again removes the like instead of stacking another
    existing = query(
        "SELECT 1 FROM post_likes WHERE user_id = %s AND post_id = %s",
        (user_id, post_id),
        fetchone=True
    )

    if existing:
        query("DELETE FROM post_likes WHERE user_id = %s AND post_id = %s", (user_id, post_id), fetch=False)
        query("UPDATE posts SET likes = likes - 1 WHERE id = %s", (post_id,), fetch=False)
        return True, "Post unliked"

    query("INSERT INTO post_likes (user_id, post_id) VALUES (%s, %s)", (user_id, post_id), fetch=False)
    query("UPDATE posts SET likes = likes + 1 WHERE id = %s", (post_id,), fetch=False)
    return True, "Post liked"

def view_posts(user_id=None):
    # using join to group together the post with the username, plus whether the current user has liked it
    return query(
        """
        SELECT posts.id, posts.content, posts.likes, posts.created_at, users.username,
               EXISTS(SELECT 1 FROM post_likes pl WHERE pl.post_id = posts.id AND pl.user_id = %s) AS liked_by_me
        FROM posts JOIN users ON users.id = posts.user_id ORDER BY posts.created_at DESC
        """,
        (user_id,)
    )

# currently for testingr4
if __name__ == "__main__":
    print("Gold-Rush-Exchange Post System")
    print("------------------------------")
