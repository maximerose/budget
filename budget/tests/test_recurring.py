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
from budget.services.forecast import get_target_account_for_expense


class RecurringExpenseModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.category = Category.objects.create(
            name="Loyer",
            owner=self.member,
        )
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_recurring_expense_str_and_remaining_amount(self) -> None:
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

    def test_recurring_expense_share_validation_exceeds_total(self) -> None:
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
        share1.full_clean()
        share1.save()

        # Deuxième part de 200€ (Total = 600 > 500, doit échouer)
        share2 = RecurringExpenseShare(
            recurring_expense=expense,
            bank_account=self.bank_account,
            amount=Decimal("200.00"),
        )

        with self.assertRaises(ValidationError):
            share2.full_clean()

    def test_get_target_bank_account_fallback(self) -> None:
        """Vérifie la déduction du compte cible si aucune répartition (share) n'existe."""
        expense = RecurringExpense.objects.create(
            label="Internet",
            total_amount=Decimal("30.00"),
            category=self.category,
        )

        # 1. Ni la charge ni la catégorie n'ont de compte par défaut.
        # Le système doit prendre le compte principal du membre (is_default=True)
        self.bank_account.is_default = True
        self.bank_account.save()
        self.assertEqual(
            get_target_account_for_expense(expense, self.member), self.bank_account
        )

        # 2. La catégorie a un compte par défaut (prioritaire sur le compte principal)
        category_account = BankAccount.objects.create(
            name="Compte Catégorie",
            account_type=AccountType.CHECKING,
            owner=self.member,
        )
        self.category.default_bank_account = category_account
        self.category.save()
        self.assertEqual(
            get_target_account_for_expense(expense, self.member), category_account
        )

        # 3. La charge a un compte par défaut (priorité absolue)
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
