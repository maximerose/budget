class Expense:
    def __init__(self, amount: float, label: str, category: str) -> None:
        self.amount = amount
        self.label = label
        self.category = category

    def to_dict(self) -> dict:
        return {"amount": self.amount, "label": self.label, "category": self.category}

    @classmethod
    def from_dict(cls, data: dict) -> "Expense":
        return cls(
            amount=data["amount"], label=data["label"], category=data["category"]
        )

    def __str__(self) -> str:
        return f"{self.category}: {self.amount}€ ({self.label})"


def display_expenses(expenses: list[Expense]) -> None:
    for index, expense in enumerate(expenses, start=1):
        print(
            f"{index}. {expense})"
        )
    print("\n")


def calculate_total(expenses: list[Expense]) -> float:
    return sum(expense.amount for expense in expenses)


def filter_by_category(expenses: list[Expense], category_name: str) -> list[Expense]:
    return [
        expense
        for expense in expenses
        if expense.category.lower().strip() == category_name.lower().strip()
    ]
