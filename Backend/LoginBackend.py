"""
- Passwords will be hashed using bcrypt insteaf of raw SHA-256 so two users with the same password have different hashes
- Login uses charlotte email address and not the username (username is still stored and used for display)
"""

import json
import hashlib
import re
import bcrypt
from pathlib import Path
from db import query

# matching emails in order to fit the charlotte.edu requirement
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@charlotte\.edu$")






def valid_charlotte_email(email):
    """
    Check that the email uses a @charlotte.edu address.
    the email or "" part prevents null values like an empty field being passed in
    """
    return bool(EMAIL_PATTERN.fullmatch(email or ""))
    
    # return bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@charlotte\.edu", email))

"""Create a new account and save it to users data.json."""
def create_account(username, email, password):
    
    if not username or not email or not password:
        return False, "All fields are required."
    # rejecting anything that isnt a charlotte.edu email
    if not valid_charlotte_email(email):
        return False, "Email must end with @charlotte.edu."

    # data = load_users()

    # check database for username OR email that is already taken (both are unique in schema.sql
    existing = query(
        "SELECT id FROM users WHERE username = %s OR email = %s",
        (username, email.lower()), # store and compare email in lowercase
        fetchone=True
    )

    if existing:
        return False, "An account with that username or email already exists."

    # bcrypt salt hashing
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    query(
        "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
        (username, email.lower(), password_hash),
        fetch=False # INSERT doesnt need to return any rows
    )
    return True, "Account created successfully"


"""Check the email and password against users data.json."""
# this login function will be used for testing for now
def login(email, password):
    success, message, _ = login_and_get_user(email, password)
    return success, message

"""
- Will be used by Flask eventually
- Loggin in is by email but the session will store the username
"""
def login_and_get_user(email, password):
    # look up account by email
    user = query(
            "SELECT id, username, password_hash FROM users WHERE email = %s",
            (email.lower(),),
            fetchone=True
        )
    if not user:
        return False, "Invalid email or password", None

    # bcrypt.checkpw will re-hash the typed password then compares it
    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return False, "Invalid email or password.", None 

    # Success -> hand back the id and username so the app.py can eventually use to set the session
    return True, "Login successful.", {"id": user["id"], "username": user["username"]}
        

def get_user_reputation(user_id):
    # calling each time the dashboard will load to the reputation shown is current
    row = query("SELECT reputation FROM users WHERE id = %s", (user_id,), fetchone=True)
    return row["reputation"] if row else None
 

# content below runs when executing this file directly, not when app.py uses it
# for testing for now
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
