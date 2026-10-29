from datetime import datetime, timezone

import psycopg2

from db import query, transaction
import AchievementBackend as achievements

# picks on games with no result this many days after the start time get refunded
VOID_AFTER_DAYS = 5

# how many of everyone's picks the predictions feed shows
COMMUNITY_LIMIT = 100


def create_prediction(user_id, game_id, pick, points):
    # place a pick. returns (ok, message)
    # reject empty game/prediction text before it gets to the db
    if not game_id or pick not in ("home", "away"):
        return False, "A game and a pick (home or away) are required."

    # points has to be positive
    if points is None or points <= 0:
        return False, "Points wagered must be more than 0"

    game = query("SELECT home_team, away_team, status, start_time FROM games WHERE id = %s", (game_id,), fetchone=True)
    if not game:
        return False, "That game does not exist"

    if game["status"] != "scheduled" or game["start_time"] <= datetime.now(timezone.utc):
        return False, "Predictions are closed for this game."

    display_game = f"{game['away_team']} @ {game['home_team']}"
    display_pick = game["home_team"] if pick == "home" else game["away_team"]

    try:
        # checking for an existing pick, holding the wager and saving the pick all happen together
        with transaction() as tx:
            # one pick per game (refunded picks don't count)
            if tx.query("SELECT 1 FROM predictions WHERE user_id = %s AND game_id = %s AND result <> 'void'",
                        (user_id, game_id), fetchone=True):
                return False, "You already made a pick for this game."

            held = tx.query(
                "UPDATE users SET reputation = reputation - %s WHERE id = %s AND reputation >= %s RETURNING reputation",
                (points, user_id, points),
                fetchone=True,
            )
            if not held:
                return False, "You do not have enough reputation points to make that prediction."

            # no result value is given (it will be pending at first)
            tx.query(
                "INSERT INTO predictions (user_id, game, prediction_text, points, game_id, pick) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, display_game, f"{display_pick} wins", points, game_id, pick),
                fetch=False,
            )
    except psycopg2.errors.UniqueViolation:
        return False, "You already made a pick for this game."
    return True, "Prediction created successfully."


def _settle_one(prediction_id, result, payout):
    # only matches a pick that's still pending, so two syncs at once can't pay the same pick twice
    with transaction() as tx:
        row = tx.query(
            "UPDATE predictions SET result = %s WHERE id = %s AND result = 'pending' RETURNING user_id",
            (result, prediction_id),
            fetchone=True,
        )
        if not row:
            return None
        if payout:
            tx.query("UPDATE users SET reputation = reputation + %s WHERE id = %s",
                     (payout, row["user_id"]), fetch=False)
        return row["user_id"]


# auto settle the predictions
def auto_settle_finished_games():
    pending = query(
        """
        SELECT p.id, p.user_id, p.pick, p.points, g.status, g.home_score, g.away_score,
               g.start_time < now() - make_interval(days => %s) AS stale
        FROM predictions p
        JOIN games g ON g.id = p.game_id
        WHERE p.result = 'pending'
          AND (g.status IN ('final', 'canceled') OR g.start_time < now() - make_interval(days => %s))
        """,
        (VOID_AFTER_DAYS, VOID_AFTER_DAYS),
    )
    settled = 0
    # remember whose picks were settled so their achievements are checked once each
    settled_users = set()
    for p in pending:
        final_with_scores = p["status"] == "final" and p["home_score"] is not None and p["away_score"] is not None
        if not final_with_scores:
            if p["status"] == "canceled" or p["stale"]:
                result, payout = "void", p["points"]  # refund the wager
            else:
                continue  # final but no scores yet: wait for the next sync
        elif p["home_score"] == p["away_score"]:
            result, payout = "void", p["points"]  # ties are refunded instead of waiting forever
        else:
            actual_winner = "home" if p["home_score"] > p["away_score"] else "away"
            if p["pick"] == actual_winner:
                # the wager was already deducted when placed: a win returns it plus winnings (2x)
                result, payout = "correct", p["points"] * 2
            else:
                result, payout = "incorrect", 0

        uid = _settle_one(p["id"], result, payout)
        if uid:
            settled += 1
            settled_users.add(uid)

    achievements.try_check(*settled_users)
    return settled


def view_feed(user_id=None, limit=COMMUNITY_LIMIT):
    return query(
        """
        SELECT predictions.*, users.username
        FROM predictions JOIN users ON users.id = predictions.user_id
        WHERE predictions.user_id = %s
           OR predictions.id IN (SELECT id FROM predictions ORDER BY created_at DESC LIMIT %s)
        ORDER BY predictions.created_at DESC
        """,
        (user_id, limit),
    )


if __name__ == "__main__":
    # settle anything that's ready, without starting the web server
    print(f"Settled {auto_settle_finished_games()} predictions")