import json
from pathlib import Path

POSTS_FILE = Path(__file__).parent.parent / "Data" / "PostsData.json"


def load_posts():
    if not POSTS_FILE.exists():
        return {"posts": []}

    with open(POSTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_posts(data):
    with open(POSTS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def create_post(username, content):
    if not username or not content:
        return False, "Username and post content are required."

    data = load_posts()
    new_id = len(data["posts"]) + 1

    new_post = {
        "post_id": new_id,
        "username": username,
        "content": content,
        "likes": 0
    }

    data["posts"].append(new_post)
    save_posts(data)

    return True, "Post created successfully."


def like_post(post_id):
    data = load_posts()

    for post in data["posts"]:
        if post["post_id"] == post_id:
            post["likes"] += 1
            save_posts(data)
            return True, "Post liked."

    return False, "Post not found."


def view_posts():
    data = load_posts()

    if not data["posts"]:
        print("No posts have been created yet.")
        return

    print("\n--- Posts ---")

    for post in data["posts"]:
        print(f"Post ID: {post['post_id']}")
        print(f"User: {post['username']}")
        print(f"Post: {post['content']}")
        print(f"Likes: {post['likes']}")
        print("-------------------")


if __name__ == "__main__":
    print("Gold-Rush-Exchange Post System")
    print("------------------------------")

    while True:
        print("\n1. Create Post")
        print("2. View Posts")
        print("3. Like Post")
        print("4. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            username = input("Username: ")
            content = input("Post: ")

            success, message = create_post(username, content)
            print(message)

        elif choice == "2":
            view_posts()

        elif choice == "3":
            try:
                post_id = int(input("Post ID to like: "))
            except ValueError:
                print("Please enter a valid post ID.")
                continue

            success, message = like_post(post_id)
            print(message)

        elif choice == "4":
            print("Goodbye!")
            break

        else:
            print("Invalid option.")