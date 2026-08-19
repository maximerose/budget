from decimal import Decimal

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