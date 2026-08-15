import json


def load_expenses(filename: str) -> list[dict]:
    try:
        with open(filename, "r") as file:
            expenses = json.load(file)
            return expenses
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_expenses(expenses: list[dict], filename: str) -> None:
    try:
        with open(filename, "w") as file:
            json.dump(expenses, file, indent=4)
    except FileNotFoundError:
        print("Fichier introuvable")
