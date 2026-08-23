from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    RecurringExpense,
)


class CategoryModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.category = Category.objects.create(name="Loyer", owner=self.member)
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
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.category,
        )
        self.category.delete()
        expense.refresh_from_db()
        self.assertIsNone(expense.category)

    def test_category_income_and_meal_voucher_validation(self) -> None:
        # 1. Catégorie de revenu valide (is_income=True, is_meal_voucher_eligible=False)
        income_cat = Category(
            name="Salaire",
            is_income=True,
            is_meal_voucher_eligible=False,
            owner=self.member,
        )
        income_cat.full_clean()  # Ne doit pas lever d'erreur
        income_cat.save()
        self.assertTrue(income_cat.is_income)
        self.assertFalse(income_cat.is_meal_voucher_eligible)

        # 2. Catégorie de dépense éligible Swile valide (is_income=False, is_meal_voucher_eligible=True)
        expense_cat = Category(
            name="Courses",
            is_income=False,
            is_meal_voucher_eligible=True,
            owner=self.member,
        )
        expense_cat.full_clean()  # Ne doit pas lever d'erreur
        expense_cat.save()
        self.assertFalse(expense_cat.is_income)
        self.assertTrue(expense_cat.is_meal_voucher_eligible)

        # 3. Catégorie invalide : is_income=True et is_meal_voucher_eligible=True (doit échouer)
        invalid_cat = Category(
            name="Invalide",
            is_income=True,
            is_meal_voucher_eligible=True,
            owner=self.member,
        )
        with self.assertRaises(ValidationError):
            invalid_cat.full_clean()

    def test_category_default_bank_account(self) -> None:
        # Vérifie qu'une catégorie peut avoir un compte bancaire par défaut
        category = Category.objects.create(
            name="Courses",
            default_bank_account=self.bank_account,
            owner=self.member,
        )
        self.assertEqual(category.default_bank_account, self.bank_account)
