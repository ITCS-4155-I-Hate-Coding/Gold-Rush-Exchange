import json
from pathlib import Path

PREDICTIONS_FILE = Path(__file__).parent.parent / "Data" / "PredictionsData.json"


def load_predictions():
    if not PREDICTIONS_FILE.exists():
        return {"predictions": []}

    with open(PREDICTIONS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_predictions(data):
    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def create_prediction(username, game, prediction, points):
    data = load_predictions()

    new_id = len(data["predictions"]) + 1

    new_prediction = {
        "prediction_id": new_id,
        "username": username,
        "game": game,
        "prediction": prediction,
        "points": points,
        "result": "Pending"
    }

    data["predictions"].append(new_prediction)
    save_predictions(data)

    return True, "Prediction created successfully."


def view_predictions():
    data = load_predictions()

    if not data["predictions"]:
        print("No predictions have been created yet.")
        return

    print("\n--- Predictions ---")

    for prediction in data["predictions"]:
        print(f"ID: {prediction['prediction_id']}")
        print(f"User: {prediction['username']}")
        print(f"Game: {prediction['game']}")
        print(f"Prediction: {prediction['prediction']}")
        print(f"Points: {prediction['points']}")
        print(f"Result: {prediction['result']}")
        print("-------------------")


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