"""
- Passwords will be hashed using bcrypt insteaf of raw SHA-256 so two users with the same password have different hashes
- Login uses charlotte email address and not the username (username is still stored and used for display)
"""

import re
import threading
import time

import bcrypt
from db import query

# matching emails in order to fit the charlotte.edu requirement
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@charlotte\.edu$", re.IGNORECASE) # ignoring capitals in email address

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.]{3,20}")

PASSWORD_MIN = 8
PASSWORD_MAX_BYTES = 72

LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW = 15 * 60
_failures = {}  # email -> list of failure times
_failures_lock = threading.Lock()

LOGIN_FAILED = "Invalid email or password."

_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())


def valid_charlotte_email(email):
    """
    Check that the email uses a @charlotte.edu address.
    the email or "" part prevents null values like an empty field being passed in
    """
    return bool(EMAIL_PATTERN.fullmatch(email or ""))


def valid_username(username):
    return bool(USERNAME_PATTERN.fullmatch(username or ""))


def create_account(username, email, password):
    # create a new account. returns (ok, message)
    username = (username or "").strip()
    email = (email or "").strip()

    if not username or not email or not password:
        return False, "All fields are required."
    if not valid_username(username):
        return False, "Usernames are 3-20 characters: letters, numbers, _ and . only."
    # rejecting anything that isnt a charlotte.edu email
    if not valid_charlotte_email(email):
        return False, "Email must end with @charlotte.edu."
    if len(password) < PASSWORD_MIN:
        return False, f"Passwords must be at least {PASSWORD_MIN} characters."
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return False, "That password is too long (72 characters at most)."

    existing = query(
        "SELECT id FROM users WHERE lower(username) = lower(%s) OR email = %s",
        (username, email.lower()),  # store and compare email in lowercase
        fetchone=True,
    )
    if existing:
        return False, "An account with that username or email already exists."

    # bcrypt salt hashing
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    query(
        "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
        (username, email.lower(), password_hash),
        fetch=False,  # INSERT doesnt need to return any rows
    )
    return True, "Account created successfully"


def login(email, password):
    # wrapper used by the terminal test menu at the bottom of this file
    success, message, _ = login_and_get_user(email, password)
    return success, message


def _too_many_failures(email):
    now = time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(email, []) if now - t < LOGIN_WINDOW]
        _failures[email] = recent
        return len(recent) >= LOGIN_MAX_FAILURES


def _record_failure(email):
    with _failures_lock:
        _failures.setdefault(email, []).append(time.time())


def login_and_get_user(email, password):
    # check an email and password. returns (ok, message, {"id", "username"} or None)
    email = (email or "").strip().lower()
    password = password or ""

    if _too_many_failures(email):
        return False, "Too many failed attempts. Try again in 15 minutes.", None

    # look up account by email
    user = query(
        "SELECT id, username, password_hash FROM users WHERE email = %s",
        (email,),
        fetchone=True,
    )
    stored = user["password_hash"].encode("utf-8") if user else _DUMMY_HASH
    # bcrypt.checkpw re-hashes the typed password and compares it.
    # (the length check avoids bcrypt errors on absurdly long input)
    ok = len(password.encode("utf-8")) <= PASSWORD_MAX_BYTES and bcrypt.checkpw(password.encode("utf-8"), stored)
    if not user or not ok:
        _record_failure(email)
        return False, LOGIN_FAILED, None

    with _failures_lock:
        _failures.pop(email, None)  # a successful login clears the count
    return True, "Login successful.", {"id": user["id"], "username": user["username"]}


def get_user_reputation(user_id):
    # read fresh each time /api/me is called so the balance shown is current
    row = query("SELECT reputation FROM users WHERE id = %s", (user_id,), fetchone=True)
    return row["reputation"] if row else None


# content below runs when executing this file directly, not when App.py uses it
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