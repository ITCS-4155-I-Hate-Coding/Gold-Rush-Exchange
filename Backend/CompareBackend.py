from db import query

# the most friends that can be compared against you at once
MAX_FRIENDS = 5


def get_comparison(user_id, usernames):
    # clean the list: trim, drop blanks and duplicates, keep the order the user picked
    names = []
    for name in usernames:
        name = name.strip()
        if name and name not in names:
            names.append(name)
    if len(names) > MAX_FRIENDS:
        return None, f"You can compare with up to {MAX_FRIENDS} friends."

    # only people you follow can be compared
    friend_ids = {}
    if names:
        friends = query(
            """
            SELECT u.id, u.username
            FROM follows f
            JOIN users u ON u.id = f.followed_id
            WHERE f.follower_id = %s AND u.username = ANY(%s)
            """,
            (user_id, names),
        )
        friend_ids = {f["username"]: f["id"] for f in friends}
        missing = [n for n in names if n not in friend_ids]
        if missing:
            return None, "You can only compare with people you follow: " + ", ".join(missing)

    ids = [user_id] + [friend_ids[n] for n in names]  # you first, then friends in picked order

    # reputation plus prediction counts for everyone in one query
    rows = query(
        """
        SELECT u.id, u.username, u.reputation,
               COUNT(p.id) AS total,
               COUNT(p.id) FILTER (WHERE p.result = 'correct')   AS correct,
               COUNT(p.id) FILTER (WHERE p.result = 'incorrect') AS incorrect,
               COUNT(p.id) FILTER (WHERE p.result = 'pending')   AS pending,
               COALESCE(SUM(p.points) FILTER (WHERE p.result = 'correct'), 0)   AS rep_gained,
               COALESCE(SUM(p.points) FILTER (WHERE p.result = 'incorrect'), 0) AS rep_lost
        FROM users u
        LEFT JOIN predictions p ON p.user_id = u.id
        WHERE u.id = ANY(%s)
        GROUP BY u.id, u.username, u.reputation
        """,
        (ids,),
    )
    by_id = {r["id"]: r for r in rows}
    return [_stats(by_id[i], i == user_id) for i in ids if i in by_id], None


def _stats(row, is_me):
    # win/loss percentages only count settled predictions, pending ones haven't been decided
    settled = row["correct"] + row["incorrect"]
    win_pct = round(row["correct"] * 100 / settled, 1) if settled else None
    loss_pct = round(100 - win_pct, 1) if settled else None
    return {
        "username": row["username"],
        "is_me": is_me,
        "reputation": row["reputation"],
        "total": row["total"],
        "correct": row["correct"],
        "incorrect": row["incorrect"],
        "pending": row["pending"],
        "settled": settled,
        "accuracy": win_pct,  # accuracy and win % are the same number: correct / settled
        "win_pct": win_pct,
        "loss_pct": loss_pct,
        "rep_gained": row["rep_gained"],
        "rep_lost": row["rep_lost"],
    }