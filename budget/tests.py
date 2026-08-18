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


class BudgetModelsTestCase(TestCase):
    def setUp(self) -> None:
        # Creation des données de base pour les tests
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.category = Category.objects.create(name="Loyer")
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_category_str(self):
        self.assertEqual(str(self.category), "Loyer")

    def test_bank_account_str(self):
        self.assertEqual(str(self.bank_account), "Compte courant (Compte courant)")

    def test_recurring_expense_str_and_remaining_amount(self):
        # Création d'une charge de 600€
        expense = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            frequency_months=1,
            category=self.category,
        )
        self.assertEqual(str(expense), "Loyer (600.00 €)")

        # Au début, il reste 600€ à répartir
        self.assertEqual(expense.get_remaining_amount_to_split(), Decimal("600.00"))

        # Ajout d'une part de 300€
        RecurringExpenseShare.objects.create(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("300.00"),
        )

        # Il doit rester 300€ à répartir
        self.assertEqual(expense.get_remaining_amount_to_split(), Decimal("300.00"))

    def test_recurring_expense_share_validation_exceeds_total(self):
        expense = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("500.00"),
            frequency_months=1,
            category=self.category,
        )

        # Première part de 400€ (OK)
        share1 = RecurringExpenseShare(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("400.00"),
        )
        share1.full_clean()  # Valide les contraintes et appelle clean()
        share1.save()

        # Deuxième part de 200€ (Total = 600 > 500, doit échouer)
        share2 = RecurringExpenseShare(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("200.00"),
        )

        with self.assertRaises(ValidationError):
            share2.full_clean()

    def test_category_protect_deletion(self):
        # Vérifie qu'on ne peut pas supprimer une catégorie liée à une charge récurrente
        RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.category,
        )

        with self.assertRaises(Exception):
            self.category.delete()
