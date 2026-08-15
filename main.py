from storage import load_expenses, save_expenses
from expenses import (
    calculate_total,
    create_expense,
    display_expenses,
    filter_by_category,
)

EXPENSES_JSON = "expenses.json"


def main():
    menu = [
        "1. Ajouter une dépense",
        "2. Lister toutes les dépenses",
        "3. Afficher le total des dépenses",
        "4. Filtrer et lister les dépenses d'une catégorie",
        "5. Quitter",
    ]

    expenses = load_expenses(EXPENSES_JSON)

    while True:
        print("Que voulez-vous faire ?")
        for item in menu:
            print(item)

        choice = input()
        match choice:
            case "1":
                print("Ajout d'une dépense")
                while True:
                    value = input("Montant de la dépense : ").replace(",", ".")
                    try:
                        amount = float(value)
                        break
                    except ValueError:
                        print(
                            "Erreur : Ce n'est pas un nombre valide (ex: 12,50 ou 12.50)"
                        )
                title = input("Libellé de la dépense : ")
                category = input("Catégorie de de la dépense : ")
                expenses.append(create_expense(amount, title, category))
                save_expenses(expenses, EXPENSES_JSON)
                print("Dépense ajoutée\n")

            case "2":
                print("Liste des dépenses")
                display_expenses(expenses)

            case "3":
                print(f"Total des dépenses : {calculate_total(expenses)}€\n")

            case "4":
                category_name = input("Saisissez la catégorie : ")
                expenses_by_category = filter_by_category(expenses, category_name)

                if expenses_by_category:
                    display_expenses(expenses_by_category)
                else:
                    print("Aucune dépense dans cette catégorie")

            case "5":
                print("Au revoir")
                return

            case _:
                print("Erreur : Ce choix n'est pas valide")


if __name__ == "__main__":
    main()
