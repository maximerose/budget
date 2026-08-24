from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    RecurringExpense,
    RecurringExpenseShare,
)
from budget.models.account import Household
from budget.models.category import CategoryType
from budget.services.forecast import get_target_account_for_expense


class RecurringExpenseModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime", household=self.household
        )
        self.category = Category.objects.create(
            name="Loyer",
            type=CategoryType.RECURRING,
            household=self.household,
        )
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_recurring_expense_str_and_remaining_amount(self) -> None:
        expense = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            frequency_months=1,
            category=self.category,
        )
        self.assertEqual(str(expense), "Loyer (600.00 €)")
        self.assertEqual(expense.get_remaining_amount_to_split(), Decimal("600.00"))

        RecurringExpenseShare.objects.create(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("300.00"),
        )
        self.assertEqual(expense.get_remaining_amount_to_split(), Decimal("300.00"))

    def test_recurring_expense_share_validation_exceeds_total(self) -> None:
        expense = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("500.00"),
            frequency_months=1,
            category=self.category,
        )

        share1 = RecurringExpenseShare(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("400.00"),
        )
        share1.full_clean()
        share1.save()

        share2 = RecurringExpenseShare(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("200.00"),
        )

        with self.assertRaises(ValidationError):
            share2.full_clean()

    def test_get_target_bank_account_fallback(self) -> None:
        expense = RecurringExpense.objects.create(
            label="Internet",
            total_amount=Decimal("30.00"),
            category=self.category,
        )

        # 1. Pas de compte par défaut défini sur la charge
        # Le système doit prendre le compte principal du membre (is_default=True)
        self.bank_account.is_default = True
        self.bank_account.save()
        self.assertEqual(
            get_target_account_for_expense(expense, self.member), self.bank_account
        )

        # 2. La charge a un compte par défaut (priorité absolue)
        expense_account = BankAccount.objects.create(
            name="Compte Charge",
            account_type=AccountType.CHECKING,
            owner=self.member,
        )
        expense.default_bank_account = expense_account
        expense.save()
        self.assertEqual(
            get_target_account_for_expense(expense, self.member), expense_account
        )
