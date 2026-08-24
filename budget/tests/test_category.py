from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    RecurringExpense,
)
from budget.models.account import Household
from budget.models.category import CategoryType


class CategoryModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime", household=self.household
        )
        self.category = Category.objects.create(
            name="Loyer", type=CategoryType.RECURRING, household=self.household
        )
        self.bank_account = BankAccount.objects.create(
            name="Compte joint",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("2000.00"),
        )

    def test_category_str(self) -> None:
        self.assertEqual(str(self.category), "Loyer")

    def test_category_protect_deletion(self) -> None:
        expense = RecurringExpense.objects.create(
            label="Loyer", total_amount=Decimal("600.00"), category=self.category
        )
        self.category.delete()
        expense.refresh_from_db()
        self.assertIsNone(expense.category)

    def test_category_income_and_meal_voucher_validation(self) -> None:
        income_cat = Category(
            name="Salaire",
            type=CategoryType.INCOME,
            is_meal_voucher_eligible=False,
            household=self.household,
        )
        income_cat.full_clean()
        income_cat.save()
        self.assertFalse(income_cat.is_meal_voucher_eligible)

        expense_cat = Category(
            name="Courses",
            type=CategoryType.VARIABLE,
            is_meal_voucher_eligible=True,
            household=self.household,
        )
        expense_cat.full_clean()
        expense_cat.save()
        self.assertTrue(expense_cat.is_meal_voucher_eligible)

        invalid_cat = Category(
            name="Invalide",
            type=CategoryType.INCOME,
            is_meal_voucher_eligible=True,
            household=self.household,
        )
        with self.assertRaises(ValidationError):
            invalid_cat.full_clean()
