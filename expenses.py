def create_expense(amount: float, title: str, category: str) -> dict:
    return {"amount": amount, "title": title, "category": category}


def display_expenses(expenses: list[dict]) -> None:
    for index, expense in enumerate(expenses, start=1):
        print(
            f"{index}. {expense['category']}: {expense['amount']}€ ({expense['title']})"
        )
    print("\n")


def calculate_total(expenses: list[dict]) -> float:
    return sum(expense["amount"] for expense in expenses)


def filter_by_category(expenses: list[dict], category_name: str) -> list[dict]:
    return [
        expense
        for expense in expenses
        if expense["category"].lower().strip() == category_name.lower().strip()
    ]
