from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from budget.models.account import AccountType, BankAccount, HouseholdMember
from budget.models.category import Category
from budget.models.transaction import Transaction


class TransactionViewsTestCase(TestCase):
    def setUp(self) -> None:
        # Création des données de base nécessaires pour que les vues fonctionnent
        self.member = HouseholdMember.objects.create(name="Maxime")

        self.account = BankAccount.objects.create(
            name="Compte Courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

        self.category = Category.objects.create(
            name="Alimentation",
            is_income=False,
            owner=self.member,
        )

    # --- TESTS POUR L'AJOUT D'UNE DÉPENSE RAPIDE ---
    def test_quick_expense_get(self) -> None:
        """Vérifie que la requête GET renvoie bien la modale de dépense rapide."""
        url = reverse("quick_expense_form")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "budget/partials/transactions/_modal_quick_expense.html"
        )

    def test_quick_expense_post(self) -> None:
        """Vérifie que la requête POSTcrée bien une transaction et demande à HTMX de rafraîchir."""
        url = reverse("quick_expense_form")
        today = timezone.localdate()

        data = {
            "total_amount": "45.50",
            "label": "Boulangerie",
            "category": str(self.category.id),
            "bank_account": str(self.account.id),
            "transaction_date": today.strftime("%Y-%m-%d"),
        }

        response = self.client.post(url, data)

        # 1. Vérification de la réponse spécifique à HTMX
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")

        # 2. Vérification de la création en base de données
        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.first()
        self.assertEqual(transaction.total_amount, Decimal("45.50"))
        self.assertEqual(transaction.label, "Boulangerie")
        self.assertEqual(transaction.category, self.category)

        # 2. Vérification que la méthode save() de Transaction a bien mis à jour le solde
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal("954.50"))

    # --- TESTS POUR L'AJUSTEMENT DU SOLDE ---
    def test_adjust_balance_get(self) -> None:
        """Vérifie que la requête GET renvoie bien la modale d'ajustement de solde."""
        url = reverse("adjust_account_balance", args=[self.account.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "budget/partials/accounts/_modal_adjust_balance.html"
        )

    def test_adjust_balance_post(self) -> None:
        """Vérifie que la requête POST met à jour le solde du compte et demande à HTMX de rafraîchir."""
        url = reverse("adjust_account_balance", args=[self.account.id])

        data = {"new_balance": "1250.00"}

        response = self.client.post(url, data)

        # 1. Vérifications HTMX
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")

        # 2. Vérification de la mise à jour direct en base de données
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal("1250.00"))
