import json
from pathlib import Path
from db import query


def create_prediction(user_id, game, prediction_text, points):
    # reject empty game/prediction text before it gets to the db
    if not game or not prediction_text:
        return False, "Game and prediction are required"

    # points has to be positive
    if points is None or points <= 0:
        return False, "Points wagered must be more than 0"

    # No result column value is given (it will be pending at first)
    query(
        "INSERT INTO predictions (user_id, game, prediction_text, points) VALUES (%s, %s, %s, %s)",
        (user_id, game, prediction_text, points),
        fetch=False,
    )
    return True, "Prediction created successfully."



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

    # for correct guess; gain wagered points and for a wrong guess you lose them
    reputation_change = prediction["points"] if is_correct else -prediction["points"]

    # updating the db to lock in the predictions result and another to change the users reputation
    query(
        "UPDATE predictions SET result = %s WHERE id = %s",
        (result, prediction_id),
        fetch=False
    )
    query(
        "UPDATE users SET reputation = reputation + %s WHERE id = %s",
        (reputation_change, prediction["user_id"]),
        fetch=False
    )

    # confirmation message
    sign = "+" if reputation_change >= 0 else ""
    return True, f"Prediction marked as {result} ({sign}{reputation_change} reputation)."


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