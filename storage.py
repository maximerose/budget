import json

from expenses import Expense


def load_expenses(filename: str) -> list[Expense]:
    try:
        with open(filename, "r") as file:
            raw_data = json.load(file)
            return [Expense.from_dict(item) for item in raw_data]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_expenses(expenses: list[Expense], filename: str) -> None:
    try:
        with open(filename, "w") as file:
            raw_data = [expense.to_dict() for expense in expenses]
            json.dump(raw_data, file, indent=4)
    except FileNotFoundError:
        print("Fichier introuvable")
