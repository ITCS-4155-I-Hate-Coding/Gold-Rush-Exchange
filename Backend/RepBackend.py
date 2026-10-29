"""
Prediction results will still be the main way to earn reputation points but on top of that there will be small rewards to encourage people to take part in the community

    post            +5 rep   for up to 3 posts in any 24 hours    (post must be 15+ characters)
    comment         +2 rep   for up to 10 comments in any 24 hours (on someone else's post, 5+ characters)
    like received   +1 rep   for up to 20 likes in any 24 hours   (from someone else)

These rep amounts mean that users can earn up to 55 rep points each day by doing small things so if they ever run out of rep or just want to be more apart of the community

To prevent spam:
    - There are daily caps
    - There are unique keys given to each so that way in the database it wont accept another row with the same key
    - Liking or commenting on your own post doesnt do anything

For the time being there will be a feature to "top off your points" if you drop to 0 so that users can still wager rep points but this may be changed in the future

"""

import time

from db import query

REWARDS = {
    "post":          {"amount": 5, "daily_cap": 3,  "min_length": 15},
    "comment":       {"amount": 2, "daily_cap": 10, "min_length": 5},
    "like_received": {"amount": 1, "daily_cap": 20, "min_length": 0},
}

TOP_UP_FLOOR = 50

# One statement does everything, so it's atomic: insert the ledger row only if the user is under
# the 24-hour cap (and ON CONFLICT skips keys that already paid), then add exactly what was
# inserted to their balance. If no row is inserted, the UPDATE changes nothing.
_AWARD_SQL = """
WITH ins AS (
    INSERT INTO rep_events (user_id, kind, source_key, amount)
    SELECT %(uid)s, %(kind)s, %(key)s, %(amount)s
    WHERE (SELECT COUNT(*) FROM rep_events
           WHERE user_id = %(uid)s AND kind = %(kind)s
             AND created_at > now() - interval '24 hours') < %(cap)s
    ON CONFLICT (source_key) DO NOTHING
    RETURNING user_id, amount
)
UPDATE users SET reputation = reputation + ins.amount
FROM ins WHERE users.id = ins.user_id
RETURNING ins.amount
"""


def _award(kind, user_id, source_key, tx=None):
    """Pay one reward. Returns the amount paid (0 if capped or already paid).
    tx: pass a transaction from db.transaction() to make the reward part of a bigger change."""
    r = REWARDS[kind]
    params = {"uid": user_id, "kind": kind, "key": source_key, "amount": r["amount"], "cap": r["daily_cap"]}
    run = tx.query if tx else query
    row = run(_AWARD_SQL, params, fetchone=True)
    return row["amount"] if row else 0


def _result(kind, awarded, reason=None):
    """What the page shows after a post or comment, e.g. '+5 rep' or why nothing was earned."""
    r = REWARDS[kind]
    if awarded:
        return {"rep_awarded": awarded, "rep_note": f"+{awarded} rep"}
    notes = {
        "short": f"{'Posts' if kind == 'post' else 'Comments'} of at least {r['min_length']} characters earn rep.",
        "own": "Comments on your own posts don't earn rep.",
        "capped": f"You've reached today's limit ({r['daily_cap']} {'posts' if kind == 'post' else 'comments'} earn rep per 24 hours).",
    }
    return {"rep_awarded": 0, "rep_note": notes.get(reason, "")}


def _safe(fn):
    """A rep reward must never make a post or comment fail: the post is already saved by the time
    the reward runs. If the reward hits an error it's printed and the user just gets no rep."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            print(f"[rep] reward failed: {e}")
            return {"rep_awarded": 0, "rep_note": ""}
    return wrapper


@_safe
def reward_post(user_id, post_id, content):
    if len(content.strip()) < REWARDS["post"]["min_length"]:
        return _result("post", 0, "short")
    paid = _award("post", user_id, f"post:{post_id}")
    return _result("post", paid, None if paid else "capped")


@_safe
def reward_comment(user_id, comment_id, post_author_id, content):
    if post_author_id == user_id:
        return _result("comment", 0, "own")
    if len(content.strip()) < REWARDS["comment"]["min_length"]:
        return _result("comment", 0, "short")
    paid = _award("comment", user_id, f"comment:{comment_id}")
    return _result("comment", paid, None if paid else "capped")


def reward_like(author_id, liker_id, item_type, item_id, tx=None):
    """+1 to the author when someone else likes their post or comment (once per liker per item)."""
    if not author_id or author_id == liker_id:
        return 0
    return _award("like_received", author_id, f"like:{item_type}:{item_id}:{liker_id}", tx=tx)


def maybe_top_up(user_id):
    """Bankruptcy floor: below TOP_UP_FLOOR with nothing pending -> back up to TOP_UP_FLOOR,
    at most once per 24 hours. Returns the amount added (0 if not needed)."""
    row = query(
        """
        WITH me AS (
            SELECT id, reputation FROM users
            WHERE id = %(uid)s AND reputation < %(floor)s
              AND NOT EXISTS (SELECT 1 FROM predictions WHERE user_id = %(uid)s AND result = 'pending')
              AND NOT EXISTS (SELECT 1 FROM rep_events WHERE user_id = %(uid)s AND kind = 'top_up'
                              AND created_at > now() - interval '24 hours')
            FOR UPDATE
        ),
        ins AS (
            INSERT INTO rep_events (user_id, kind, source_key, amount)
            SELECT id, 'top_up', %(key)s, %(floor)s - reputation FROM me
            RETURNING user_id, amount
        )
        UPDATE users SET reputation = reputation + ins.amount
        FROM ins WHERE users.id = ins.user_id
        RETURNING ins.amount
        """,
        {"uid": user_id, "floor": TOP_UP_FLOOR, "key": f"top_up:{user_id}:{time.time_ns()}"},
        fetchone=True,
    )
    return row["amount"] if row else 0


def community_rep(user_id):
    """Total rep this user has earned from posts, comments and likes (shown on the profile)."""
    row = query(
        "SELECT COALESCE(SUM(amount), 0)::int AS total FROM rep_events "
        "WHERE user_id = %s AND kind IN ('post', 'comment', 'like_received')",
        (user_id,),
        fetchone=True,
    )
    return row["total"]


def get_rules():
    """The reward table, for the hint under the post box."""
    return {"rewards": REWARDS, "top_up_floor": TOP_UP_FLOOR}