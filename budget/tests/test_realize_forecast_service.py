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
from budget.models.account import Household
from budget.models.category import CategoryType
from budget.services.forecast import create_transaction_from_recurring_expense


class CreateTransactionFromRecurringExpenseTestCase(TestCase):
    def setUp(self) -> None:
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime", household=self.household
        )
        self.today = timezone.localdate().replace(day=1)

        self.account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )
        self.category = Category.objects.create(
            name="Abonnements", type=CategoryType.RECURRING, household=self.household
        )
        self.spotify = RecurringExpense.objects.create(
            label="Spotify", total_amount=Decimal("17.20"), category=self.category
        )
        self.share = RecurringExpenseShare.objects.create(
            recurring_expense=self.spotify,
            bank_account=self.account,
            amount=Decimal("17.20"),
        )

    def test_creates_transaction_from_recurring_share(self) -> None:
        tx = create_transaction_from_recurring_expense(
            expense=self.spotify,
            bank_account=self.account,
            amount=self.share.amount,
            budget_month=self.today,
        )
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(tx.label, "Spotify")
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal("982.80"))
