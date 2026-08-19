from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from budget.models import Category, RecurringExpense


class CategoryModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.category = Category.objects.create(name="Loyer")

    def test_category_str(self) -> None:
        self.assertEqual(str(self.category), "Loyer")

    def test_category_protect_deletion(self) -> None:
        # Vérifie qu'on ne peut pas supprimer une catégorie liée à une charge récurrente
        RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.category,
        )

        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_category_income_and_meal_voucher_validation(self) -> None:
        # 1. Catégorie de revenu valide (is_income=True, is_meal_voucher_eligible=False)
        income_cat = Category(
            name="Salaire", is_income=True, is_meal_voucher_eligible=False
        )
        income_cat.full_clean()  # Ne doit pas lever d'erreur
        income_cat.save()
        self.assertTrue(income_cat.is_income)
        self.assertFalse(income_cat.is_meal_voucher_eligible)

        # 2. Catégorie de dépense éligible Swile valide (is_income=False, is_meal_voucher_eligible=True)
        expense_cat = Category(
            name="Courses", is_income=False, is_meal_voucher_eligible=True
        )
        expense_cat.full_clean()  # Ne doit pas lever d'erreur
        expense_cat.save()
        self.assertFalse(expense_cat.is_income)
        self.assertTrue(expense_cat.is_meal_voucher_eligible)

        # 3. Catégorie invalide : is_income=True et is_meal_voucher_eligible=True (doit échouer)
        invalid_cat = Category(
            name="Invalide", is_income=True, is_meal_voucher_eligible=True
        )
        with self.assertRaises(ValidationError):
            invalid_cat.full_clean()
