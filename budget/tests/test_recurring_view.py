from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from budget.models.account import AccountType, BankAccount, HouseholdMember
from budget.models.category import Category
from budget.models.recurring import RecurringExpense
from budget.models.transaction import Transaction


class RecurringViewTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")

        self.account = BankAccount.objects.create(
            name="Compte Courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

        self.category = Category.objects.create(
            name="Abonnements",
            is_income=False,
            owner=self.member,
        )

        self.expense = RecurringExpense.objects.create(
            label="Internet",
            total_amount=Decimal("30.00"),
            category=self.category,
            default_bank_account=self.account,
        )

    # --- TESTS DU PAIEMENT DES CHARGES RÉCURRENTES ---

    def test_pay_recurring_expense_get(self) -> None:
        """Vérifie que la modale de paiement des charges s'affiche bien."""
        url = reverse("pay_recurring_expense", args=[self.expense.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "budget/partials/recurring/_modal_pay_recurring.html"
        )
        self.assertEqual(response.context["expense"], self.expense)

    def test_pay_recurring_expense_post(self) -> None:
        """Vérifie que le paiement partiel ou total génère la bonne transaction et rafraîchit HTMX."""
        url = reverse("pay_recurring_expense", args=[self.expense.id])
        data = {
            "amount": "30.00",
            "account_id": str(self.account.id),
        }

        response = self.client.post(url, data)

        # 1. Vérifications HTMX
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")

        # 2. Vérification de la création de la transaction
        self.assertEqual(Transaction.objects.count(), 1)
        tx = Transaction.objects.first()
        self.assertEqual(tx.total_amount, Decimal("30.00"))
        self.assertEqual(tx.recurring_expense, self.expense)
        self.assertEqual(tx.bank_account, self.account)
