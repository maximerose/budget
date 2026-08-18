from database import add_expense, create_tables, get_all_expenses, load_connection
from expenses import (
    Expense,
    calculate_total,
    display_expenses,
    filter_by_category,
)


def main():
    menu = [
        "1. Ajouter une dépense",
        "2. Lister toutes les dépenses",
        "3. Afficher le total des dépenses",
        "4. Filtrer et lister les dépenses d'une catégorie",
        "5. Quitter",
    ]

    conn = load_connection()
    if not conn:
        print("Erreur : Impossible de se connecter à la base de données")
        return

    create_tables(conn)

    expenses = get_all_expenses(conn)

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
                category = input("Catégorie de de la dépense : ")
                label = input("Libellé de la dépense : ")

                new_expense = Expense(amount, category, label)
                add_expense(conn, new_expense)
                expenses.append(new_expense)

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
                conn.close()
                return

            case _:
                print("Erreur : Ce choix n'est pas valide")


if __name__ == "__main__":
    main()
