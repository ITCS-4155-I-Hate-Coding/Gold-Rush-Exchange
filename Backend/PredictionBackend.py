from datetime import datetime, timezone
import json
from pathlib import Path
from db import query
import AchievementBackend as achievements


def create_prediction(user_id, game_id, pick, points):
    # reject empty game/prediction text before it gets to the db
    if not game_id or pick not in ("home", "away") :
        return False, "A game and a pick (home or away) are required."

    # points has to be positive
    if points is None or points <= 0:
        return False, "Points wagered must be more than 0"

    
    game = query("SELECT home_team, away_team, status, start_time FROM games WHERE id = %s", (game_id,), fetchone=True)
    if not game:
        return False, "That game does not exist"

    if game["status"] != "scheduled" or game["start_time"] <= datetime.now(timezone.utc): # error here
        return False, "Predictions are closed for this game."

    display_game = f"{game['away_team']} @ {game['home_team']}"
    display_pick = game["home_team"] if pick == "home" else game["away_team"]

    # holding the wager points until the game is settled; no need to deduct them from the users reputation yet
    held = query("UPDATE users SET reputation = reputation - %s WHERE id = %s AND reputation >= %s RETURNING reputation", 
                 (points, user_id, points),
                 fetchone=True)
    if not held:
        return False, "You do not have enough reputation points to make that prediction."

    # no result column value is given (it will be pending at first)
    try:
        query("INSERT INTO predictions (user_id, game, prediction_text, points, game_id, pick) VALUES (%s, %s, %s, %s, %s, %s )",
            (user_id, display_game, f"{display_pick} wins", points, game_id, pick),
            fetch=False,)
    except Exception:
        # if the insert fails, refund the points to the user
        query("UPDATE users SET reputation = reputation + %s WHERE id = %s", 
              (points, user_id),
              fetch=False,)
        raise
    return True, "Prediction created successfully."


    # No result column value is given (it will be pending at first)
    query(
        "INSERT INTO predictions (user_id, game, prediction_text, points, game_id, pick) VALUES (%s, %s, %s, %s, %s, %s)",
        (user_id, display_game, f"{display_pick} wins", points, game_id, pick),
        fetch=False,
    )
    return True, "Prediction created successfully."


# Auto settle the predicitons
def auto_settle_finished_games():
    pending = query(
        "SELECT predictions.id, predictions.user_id, predictions.pick, predictions.points, games.home_score, games.away_score" \
        " FROM predictions JOIN games on games.id = predictions.game_id WHERE predictions.result = 'pending' AND games.status = 'final'"
    )
    settled = 0
    settled_users = set()
    for p in pending:
        if p["home_score"] == p["away_score"]:
            continue # not guessing on ties
        actual_winner = "home" if p["home_score"] > p["away_score"] else "away"
        result = "correct" if p["pick"] == actual_winner else "incorrect"

        # the wager was already deducted when placed: a win returns it plus winnings (2x), a loss pays nothing more
        payout = p["points"] * 2 if result == "correct" else 0
        query("UPDATE predictions SET result = %s WHERE id = %s",
              (result, p["id"]),
              fetch=False,)
        if payout:
            query("UPDATE users SET reputation = reputation + %s WHERE id = %s",
                  (payout, p["user_id"]),
                  fetch=False,)
        settled += 1
        settled_users.add(p["user_id"])
    achievements.try_check(*settled_users)
    return settled



# if user_id is given, then only return that users predictions
# for now in order to test it will return everyones predictions 
def view_predictions(user_id=None):

    if user_id is not None:
        return query(
            "SELECT * FROM predictions WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
    return query("SELECT * FROM predictions ORDER BY created_at DESC")

# mark a pending prediction as win or loss by comparing prediction_text to the actual outcome
def settle_prediction(prediction_id, actual_outcome):
    # pull who owns it, what they predicted, how many points wagered, and if it has been settled
    prediction = query(
        "SELECT user_id, prediction_text, points, result FROM predictions WHERE id = %s",
        (prediction_id,),
        fetchone=True,
    
    )
    if not prediction:
        return False, "Prediction not found."

    # preventing settling the same prediction twice
    if prediction["result"] != "pending":
        return False, f"Prediction was already settled as {prediction['result']}."

    # adjusting prediction_text to be in a more universal format
    is_correct = prediction["prediction_text"].strip().lower() == actual_outcome.strip().lower()
    result = "correct" if is_correct else "incorrect"

    # the wager was already deducted when placed: a correct guess gets it back plus winnings, a wrong guess gets nothing
    reputation_change = prediction["points"] * 2 if is_correct else 0

    # updating the db to lock in the predictions result and another to pay out winners
    query(
        "UPDATE predictions SET result = %s WHERE id = %s",
        (result, prediction_id),
        fetch=False
    )
    if reputation_change:
        query(
            "UPDATE users SET reputation = reputation + %s WHERE id = %s",
            (reputation_change, prediction["user_id"]),
            fetch=False
        )

    # net change compared to before the wager was placed
    net = prediction["points"] if is_correct else -prediction["points"]


    # confirmation message
    sign = "+" if net >= 0 else ""
    return True, f"Prediction marked as {result} ({sign}{net} reputation)."


if __name__ == "__main__":
    print("Gold-Rush-Exchange Prediction System")
    print("------------------------------------")

    while True:
        print("\n1. Make Prediction")
        print("2. View Predictions")
        print("3. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            username = input("Username: ")
            game = input("Game/Event: ")
            prediction = input("Your Prediction: ")

            try:
                points = int(input("Reputation Points: "))
                if points <= 0:
                    print("Points must be greater than 0.")
                    continue
            except ValueError:
                print("Please enter a valid number of points.")
                continue

            success, message = create_prediction(
                username, game, prediction, points
            )
            print(message)

        elif choice == "2":
            view_predictions()

        elif choice == "3":
            print("Goodbye!")
            break

        else:
            print("Invalid option.")