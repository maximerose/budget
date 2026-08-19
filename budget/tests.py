from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
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
    TransactionType,
    Transfer,
)
from budget.utils import calculate_budget_month


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

    def test_category_str(self) -> None:
        self.assertEqual(str(self.category), "Loyer")

    def test_bank_account_str(self) -> None:
        self.assertEqual(str(self.bank_account), "Compte courant (Compte courant)")

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

    def test_category_protect_deletion(self) -> None:
        # Vérifie qu'on ne peut pas supprimer une catégorie liée à une charge récurrente
        RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.category,
        )

        with self.assertRaises(ProtectedError):
            self.category.delete()

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

        # Test du __str__ pour une dépense
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

        # Test du __str__ pour un revenu
        expected_income_str = (
            f"[Revenu] {income_tx.transaction_date} - Loyer: +2500.00 € (Salaire)"
        )
        self.assertEqual(str(income_tx), expected_income_str)

    def test_transfer_creation_and_str(self) -> None:
        # Création d'un second compte pour le transfert
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

        # Vérifier que les soldes des comptes ont bien été mis à jour
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
        # Interdire un virement vers le même compte
        transfer = Transfer(
            source_account=self.bank_account,
            destination_account=self.bank_account,
            amount=Decimal("50.0"),
        )

        with self.assertRaises(ValidationError):
            transfer.full_clean()

    def test_transaction_budget_month_default_and_custom(self) -> None:
        # Test que par défaut, si aucun budget_month n'est précisé, c'est la date actuelle qui prime
        tx_default = Transaction.objects.create(
            total_amount=Decimal("20.00"),
            label="Achat standard",
            category=self.category,
            bank_account=self.bank_account,
        )
        self.assertEqual(tx_default.budget_month, timezone.localdate())

        # Test avec un mois précédent (ex : dernier jour du mois pour un salaire décalé)
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

        # Date de référence : 4 septembre 2026
        ref_date = datetime.date(2026, 9, 4)

        # 1. Test mois antérieur (août 2026 -> Doit donner le dernier jour : 31 août)
        past_budget_month = calculate_budget_month(ref_date, 2026, 8)
        self.assertEqual(past_budget_month, datetime.date(2026, 8, 31))

        # 2. Test mois postérieur (octobre 2026 -> Doit donner le premier jour : 1er octobre)
        next_budget_month = calculate_budget_month(ref_date, 2026, 10)
        self.assertEqual(next_budget_month, datetime.date(2026, 10, 1))

        # 3. Même mois (septembre 2026 -> Doit conserver la date de référence)
        current_budget_month = calculate_budget_month(ref_date, 2026, 9)
        self.assertEqual(current_budget_month, ref_date)
