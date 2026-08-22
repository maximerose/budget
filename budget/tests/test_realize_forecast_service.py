from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    RecurringExpense,
    RecurringExpenseShare,
    Transaction,
)
from budget.services.forecast import create_transaction_from_recurring_expense


class CreateTransactionFromRecurringExpenseTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.today = timezone.localdate().replace(day=1)

        self.account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )
        self.category = Category.objects.create(
            name="Abonnements", default_bank_account=self.account
        )
        self.spotify = RecurringExpense.objects.create(
            label="Spotify",
            total_amount=Decimal("17.20"),
            category=self.category,
        )
        self.share = RecurringExpenseShare.objects.create(
            recurring_expense=self.spotify,
            bank_account=self.account,
            amount=Decimal("17.20"),
        )

    def test_creates_transaction_from_recurring_share(self) -> None:
        # Action : validation de la charge Spotify
        tx = create_transaction_from_recurring_expense(
            share=self.share,
            budget_month=self.today,
        )

        # 1. Vérification que la transaction existe et est bien liée à Spotify
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(tx.label, "Spotify")
        self.assertEqual(tx.category, self.category)
        self.assertEqual(tx.recurring_expense, self.spotify) 
        self.assertEqual(tx.total_amount, Decimal("17.20"))

        # 2. Vérification que le compte bancaire a été débité (1000 - 17.20 = 982.80)
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal("982.80"))
