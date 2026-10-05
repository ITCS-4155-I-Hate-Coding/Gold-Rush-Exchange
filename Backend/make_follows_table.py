# run: python make_follows_table.py

from db import query

query("""
CREATE TABLE IF NOT EXISTS follows (
    follower_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, followed_id),
    CHECK (follower_id <> followed_id)
)
""", fetch=False)

query(
    "CREATE INDEX IF NOT EXISTS idx_follows_followed_id ON follows(followed_id)",
    fetch=False,
)

print("follows table is ready")
