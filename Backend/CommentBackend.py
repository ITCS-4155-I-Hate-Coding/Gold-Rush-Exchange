import json
from pathlib import Path

COMMENTS_FILE = Path(__file__).parent.parent / "Data" / "CommentsData.json"


def load_comments():
    if not COMMENTS_FILE.exists():
        return {"comments": []}

    with open(COMMENTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_comments(data):
    with open(COMMENTS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def create_comment(username, post_id, content):
    if not username or not content:
        return False, "Username and comment content are required."

    data = load_comments()
    new_id = len(data["comments"]) + 1

    new_comment = {
        "comment_id": new_id,
        "post_id": post_id,
        "username": username,
        "content": content,
        "likes": 0
    }

    data["comments"].append(new_comment)
    save_comments(data)

    return True, "Comment created successfully."


def like_comment(comment_id):
    data = load_comments()

    for comment in data["comments"]:
        if comment["comment_id"] == comment_id:
            comment["likes"] += 1
            save_comments(data)
            return True, "Comment liked."

    return False, "Comment not found."


def view_comments(post_id):
    data = load_comments()
    found = False

    print(f"\n--- Comments for Post {post_id} ---")

    for comment in data["comments"]:
        if comment["post_id"] == post_id:
            found = True
            print(f"Comment ID: {comment['comment_id']}")
            print(f"User: {comment['username']}")
            print(f"Comment: {comment['content']}")
            print(f"Likes: {comment['likes']}")
            print("-------------------")

    if not found:
        print("No comments found for this post.")


if __name__ == "__main__":
    print("Gold-Rush-Exchange Comment System")
    print("---------------------------------")

    while True:
        print("\n1. Create Comment")
        print("2. View Comments")
        print("3. Like Comment")
        print("4. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            username = input("Username: ")

            try:
                post_id = int(input("Post ID: "))
            except ValueError:
                print("Please enter a valid post ID.")
                continue

            content = input("Comment: ")

            success, message = create_comment(
                username, post_id, content
            )
            print(message)

        elif choice == "2":
            try:
                post_id = int(input("Post ID: "))
            except ValueError:
                print("Please enter a valid post ID.")
                continue

            view_comments(post_id)

        elif choice == "3":
            try:
                comment_id = int(input("Comment ID to like: "))
            except ValueError:
                print("Please enter a valid comment ID.")
                continue

            success, message = like_comment(comment_id)
            print(message)

        elif choice == "4":
            print("Goodbye!")
            break

        else:
            print("Invalid option.")
