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
    


def like_post(post_id):
    # result of liking post will update the database to show amount of likes
    result = query(
        "UPDATE posts SET likes = likes + 1 WHERE id = %s RETURNING id",
        (post_id,),
        fetchone=True
    )
    if not result:
        return False, "Post not found."
    return True, "Post liked"

def view_posts():
    # using join to group together the post with the username
    return query(
        "SELECT posts.id, posts.content, posts.likes, posts.created_at, users.username FROM posts" \
        " JOIN users ON users.id = posts.user_id ORDER BY posts.created_at DESC"
    )

# currently for testingr4
if __name__ == "__main__":
    print("Gold-Rush-Exchange Post System")
    print("------------------------------")
