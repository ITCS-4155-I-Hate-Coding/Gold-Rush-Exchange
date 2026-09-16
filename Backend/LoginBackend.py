import json
import hashlib
import re
from pathlib import Path

# users data.json is located in the data folder
USERS_FILE = Path(__file__).parent.parent / "Data" / "UsersData.json"


def load_users():
    """Load users from the JSON file."""
    if not USERS_FILE.exists():
        return {"users": []}

    with open(USERS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_users(data):
    """Save users to the JSON file."""
    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def hash_password(password):
    """Hash the password before storing it."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def valid_charlotte_email(email):
    """Check that the email uses a @charlotte.edu address."""
    return bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@charlotte\.edu", email))


def create_account(username, email, password):
    """Create a new account and save it to users data.json."""
    if not username or not email or not password:
        return False, "All fields are required."

    if not valid_charlotte_email(email):
        return False, "Email must end with @charlotte.edu."

    data = load_users()

    for user in data["users"]:
        if user["email"].lower() == email.lower():
            return False, "An account with this email already exists."

    new_user = {
        "username": username,
        "email": email.lower(),
        "password": hash_password(password)
    }

    data["users"].append(new_user)
    save_users(data)

    return True, "Account created successfully."


def login(email, password):
    """Check the email and password against users data.json."""
    data = load_users()
    password_hash = hash_password(password)

    for user in data["users"]:
        if (
            user["email"].lower() == email.lower()
            and user["password"] == password_hash
        ):
            return True, f"Login successful. Welcome, {user['username']}!"

    return False, "Invalid email or password."


if __name__ == "__main__":
    print("Gold-Rush-Exchange Login System")
    print("--------------------------------")

    while True:
        print("\n1. Create Account")
        print("2. Login")
        print("3. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            username = input("Username: ")
            email = input("Charlotte Email: ")
            password = input("Password: ")

            success, message = create_account(username, email, password)
            print(message)

        elif choice == "2":
            email = input("Charlotte Email: ")
            password = input("Password: ")

            success, message = login(email, password)
            print(message)

        elif choice == "3":
            print("Goodbye!")
            break

        else:
            print("Invalid option.")
