import datetime
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    Transaction,
    TransactionType,
    Transfer,
)
from budget.utils import calculate_budget_month


class TransactionAndTransferTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.category = Category.objects.create(name="Loyer")
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_transaction_creation_and_defaults(self) -> None:
        # Test d'une dépense
        expense_tx = Transaction.objects.create(
            total_amount=Decimal("45.50"),
            swile_amount=Decimal("15.00"),
            label="Courses Leclerc",
            category=self.category,
            bank_account=self.bank_account,
            transaction_type=TransactionType.EXPENSE,
        )

        self.assertEqual(expense_tx.transaction_type, TransactionType.EXPENSE)
        self.assertEqual(expense_tx.total_amount, Decimal("45.50"))
        self.assertEqual(expense_tx.swile_amount, Decimal("15.00"))
        self.assertEqual(expense_tx.label, "Courses Leclerc")
        self.assertIsNotNone(expense_tx.transaction_date)

        expected_expense_str = f"[Dépense] {expense_tx.transaction_date} - Loyer: -45.50 € (Courses Leclerc)"
        self.assertEqual(str(expense_tx), expected_expense_str)

        # Test d'un revenu
        income_tx = Transaction.objects.create(
            total_amount=Decimal("2500.00"),
            label="Salaire",
            category=self.category,
            bank_account=self.bank_account,
            transaction_type=TransactionType.INCOME,
        )

        self.assertEqual(income_tx.transaction_type, TransactionType.INCOME)
        expected_income_str = f"[Revenu] {income_tx.transaction_date} - Loyer: +2500.00 € (Salaire)"
        self.assertEqual(str(income_tx), expected_income_str)

    def test_transfer_creation_and_str(self) -> None:
        destination_account = BankAccount.objects.create(
            name="Livret A",
            account_type=AccountType.SAVINGS,
            owner=self.member,
            current_balance=Decimal("500.00"),
        )

        initial_source_balance = self.bank_account.current_balance
        initial_destination_balance = destination_account.current_balance

        transfer_date = timezone.localdate()
        transfer = Transfer.objects.create(
            source_account=self.bank_account,
            destination_account=destination_account,
            amount=Decimal("150.00"),
            date=transfer_date,
        )

        self.assertEqual(transfer.source_account, self.bank_account)
        self.assertEqual(transfer.destination_account, destination_account)
        self.assertEqual(transfer.amount, Decimal("150.00"))
        self.assertEqual(transfer.date, transfer_date)

        expected_str = "Transfert de 150.00 € (Compte courant -> Livret A)"
        self.assertEqual(str(transfer), expected_str)

        self.bank_account.refresh_from_db()
        destination_account.refresh_from_db()
        self.assertEqual(
            self.bank_account.current_balance,
            initial_source_balance - Decimal("150.00"),
        )
        self.assertEqual(
            destination_account.current_balance,
            initial_destination_balance + Decimal("150.00"),
        )

    def test_transfer_same_account_validation(self) -> None:
        transfer = Transfer(
            source_account=self.bank_account,
            destination_account=self.bank_account,
            amount=Decimal("50.0"),
        )

        with self.assertRaises(ValidationError):
            transfer.full_clean()

    def test_transaction_budget_month_default_and_custom(self) -> None:
        tx_default = Transaction.objects.create(
            total_amount=Decimal("20.00"),
            label="Achat standard",
            category=self.category,
            bank_account=self.bank_account,
        )
        self.assertEqual(tx_default.budget_month, timezone.localdate())

        last_day_prev_month = timezone.localdate().replace(day=1) - timedelta(days=1)
        tx_custom = Transaction.objects.create(
            total_amount=Decimal("2500.00"),
            label="Salaire mois précédent",
            category=self.category,
            bank_account=self.bank_account,
            transaction_date=timezone.localdate(),
            budget_month=last_day_prev_month,
        )
        self.assertEqual(tx_custom.budget_month, last_day_prev_month)

    def test_calculate_budget_month_logic(self) -> None:
        ref_date = datetime.date(2026, 9, 4)

        # 1. Mois antérieur -> Dernier jour
        past_budget_month = calculate_budget_month(ref_date, 2026, 8)
        self.assertEqual(past_budget_month, datetime.date(2026, 8, 31))

        # 2. Mois postérieur -> Premier jour
        next_budget_month = calculate_budget_month(ref_date, 2026, 10)
        self.assertEqual(next_budget_month, datetime.date(2026, 10, 1))

        # 3. Même mois -> Date de référence
        current_budget_month = calculate_budget_month(ref_date, 2026, 9)
        self.assertEqual(current_budget_month, ref_date)