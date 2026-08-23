from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    MonthlyForecast,
    MonthlyForecastShare,
    RecurringExpense,
    RecurringExpenseShare,
    Transaction,
    TransactionType,
)
from budget.models.recurring import RecurringExpenseStatus
from budget.services.forecast import (
    calculate_monthly_projected_balances,
    get_recurring_expenses_with_status,
)


class ForecastServiceTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.today = timezone.localdate().replace(day=1)

        self.checking_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1500.00"),
            is_default=True,
        )
        self.savings_account = BankAccount.objects.create(
            name="Livret A",
            account_type=AccountType.SAVINGS,
            owner=self.member,
            current_balance=Decimal("5000.00"),
        )
        self.tr_account = BankAccount.objects.create(
            name="Swile",
            account_type=AccountType.MEAL_VOUCHER,
            owner=self.member,
            current_balance=Decimal("100.00"),
            fallback_account=self.checking_account,
        )

        self.cat_housing = Category.objects.create(
            name="Logement",
            default_bank_account=self.checking_account,
            owner=self.member,
        )
        self.cat_groceries = Category.objects.create(
            name="Courses",
            is_meal_voucher_eligible=True,
            default_bank_account=self.checking_account,
            owner=self.member,
        )
        self.cat_salary = Category.objects.create(
            name="Salaire",
            is_income=True,
            default_bank_account=self.checking_account,
            owner=self.member,
        )
        self.cat_savings = Category.objects.create(
            name="Épargne projet",
            default_bank_account=self.savings_account,
            owner=self.member,
        )

    def test_calculate_monthly_projected_balances_complete_cascade(self) -> None:
        # 1. Charge fixe : Loyer 600€
        rent = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.cat_housing,
        )
        RecurringExpenseShare.objects.create(
            recurring_expense=rent,
            bank_account=self.checking_account,
            amount=Decimal("600.00"),
        )

        # 2. Charge variable : Courses 300€ (TR)
        forecast_groceries = MonthlyForecast.objects.create(
            month=self.today,
            category=self.cat_groceries,
            member=self.member,
            total_amount=Decimal("300.00"),
        )
        MonthlyForecastShare.objects.create(
            forecast=forecast_groceries,
            bank_account=self.checking_account,
            amount=Decimal("300.00"),
        )

        # 3. Prévision Épargne : Virement 200€ vers Livret A
        forecast_savings = MonthlyForecast.objects.create(
            month=self.today,
            category=self.cat_savings,
            member=self.member,
            total_amount=Decimal("200.00"),
        )
        MonthlyForecastShare.objects.create(
            forecast=forecast_savings,
            bank_account=self.checking_account,
            amount=Decimal("200.00"),
        )

        # 4. Prévision Revenu : Salaire 2500€
        forecast_salary = MonthlyForecast.objects.create(
            month=self.today,
            category=self.cat_salary,
            member=self.member,
            total_amount=Decimal("2500.00"),
        )
        MonthlyForecastShare.objects.create(
            forecast=forecast_salary,
            bank_account=self.checking_account,
            amount=Decimal("2500.00"),
        )

        steps = calculate_monthly_projected_balances(
            member=self.member, month=self.today
        )

        self.assertEqual(steps["initial"][self.checking_account.id], Decimal("1500.00"))
        self.assertEqual(
            steps["after_recurring"][self.checking_account.id], Decimal("900.00")
        )
        self.assertEqual(
            steps["after_variables"][self.checking_account.id], Decimal("700.00")
        )
        self.assertEqual(
            steps["after_savings"][self.checking_account.id], Decimal("500.00")
        )
        self.assertEqual(
            steps["after_savings"][self.savings_account.id], Decimal("5200.00")
        )
        self.assertEqual(
            steps["after_incomes"][self.checking_account.id], Decimal("3000.00")
        )

    def test_calculate_monthly_projected_balances_temporal_logic(self) -> None:
        current_month = self.today
        past_month = (current_month - timedelta(days=1)).replace(day=1)
        future_month = (current_month.replace(day=28) + timedelta(days=5)).replace(
            day=1
        )

        # Charge fixe : Loyer prévu à 600€
        rent = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.cat_housing,
        )
        RecurringExpenseShare.objects.create(
            recurring_expense=rent,
            bank_account=self.checking_account,
            amount=Decimal("600.00"),
        )

        # 1. MOIS PASSÉ : Loyer réellement payé 580€ en juillet
        # Transaction créée -> current_balance BDD passe de 1500€ à 920€ (1500 - 580).
        Transaction.objects.create(
            transaction_date=past_month,
            budget_month=past_month,
            total_amount=Decimal("580.00"),
            category=self.cat_housing,
            bank_account=self.checking_account,
            transaction_type=TransactionType.EXPENSE,
            recurring_expense=rent,
        )
        # Comme la transaction existe sur past_month, le réel a déjà impacté la banque.
        # after_recurring reste 920€ (pas de ré-imputation des 600€ théoriques).
        past_steps = calculate_monthly_projected_balances(
            member=self.member, month=past_month
        )
        self.assertEqual(
            past_steps["after_recurring"][self.checking_account.id], Decimal("920.00")
        )

        # 2. MOIS FUTUR : Aucune transaction sur septembre.
        # on déduit la prévision théorique (600€) du solde actuel (920€).
        # after_recurring = 920 - 600 = 320€
        future_steps = calculate_monthly_projected_balances(
            member=self.member, month=future_month
        )
        self.assertEqual(
            future_steps["after_recurring"][self.checking_account.id], Decimal("320.00")
        )

        # 3. MOIS EN COURS : Le loyer de 600€ est prélevé en août.
        # Solde BDD passe à 320€ (920 - 600).
        # La transaction existant pour août, after_recurring reste à 320€.
        Transaction.objects.create(
            transaction_date=current_month,
            budget_month=current_month,
            total_amount=Decimal("600.00"),
            category=self.cat_housing,
            bank_account=self.checking_account,
            transaction_type=TransactionType.EXPENSE,
            recurring_expense=rent,
        )
        current_steps = calculate_monthly_projected_balances(
            member=self.member, month=current_month
        )
        self.assertEqual(
            current_steps["after_recurring"][self.checking_account.id],
            Decimal("320.00"),
        )

    def test_get_recurring_expenses_with_status(self) -> None:
        rent = RecurringExpense.objects.create(
            label="Loyer",
            total_amount=Decimal("600.00"),
            category=self.cat_housing,
        )
        RecurringExpenseShare.objects.create(
            recurring_expense=rent,
            bank_account=self.checking_account,
            amount=Decimal("600.00"),
        )

        # 1. Statut initial : WAITING (0€ payé)
        result = get_recurring_expenses_with_status(self.member, self.today)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], RecurringExpenseStatus.WAITING)
        self.assertEqual(result[0]["realized_amount"], Decimal("0.00"))

        # 2. Statut après paiement partiel : PARTIAL (300€ payés)
        Transaction.objects.create(
            transaction_date=self.today,
            budget_month=self.today,
            total_amount=Decimal("300.00"),
            category=self.cat_housing,
            bank_account=self.checking_account,
            transaction_type=TransactionType.EXPENSE,
            recurring_expense=rent,
        )
        result_partial = get_recurring_expenses_with_status(self.member, self.today)
        self.assertEqual(result_partial[0]["status"], RecurringExpenseStatus.PARTIAL)
        self.assertEqual(result_partial[0]["realized_amount"], Decimal("300.00"))

        # 3. Statut après paiement complet : COMPLETED (600€ payés au total)
        Transaction.objects.create(
            transaction_date=self.today,
            budget_month=self.today,
            total_amount=Decimal("300.00"),
            category=self.cat_housing,
            bank_account=self.checking_account,
            transaction_type=TransactionType.EXPENSE,
            recurring_expense=rent,
        )
        result_completed = get_recurring_expenses_with_status(self.member, self.today)
        self.assertEqual(
            result_completed[0]["status"], RecurringExpenseStatus.COMPLETED
        )
        self.assertEqual(result_completed[0]["realized_amount"], Decimal("600.00"))

    def test_recurring_expense_without_share(self) -> None:
        """Vérifie le calcul et le statut d'une charge sans répartition (RecurringExpenseShare)."""
        # Création de la charge SANS share, liée directement au compte courant
        internet = RecurringExpense.objects.create(
            label="Internet",
            total_amount=Decimal("40.00"),
            category=self.cat_housing,
            default_bank_account=self.checking_account,
        )

        # 1. Vérification dans les projections (calculate_monthly_projecte_balances)
        steps = calculate_monthly_projected_balances(self.member, self.today)

        # Le solde initial est de 1500€. Après la charge fixe de 40€, il doit rester 1460€
        self.assertEqual(
            steps["after_recurring"][self.checking_account.id], Decimal("1460.00")
        )

        # 2. Vérification dans la liste des statuts (get_recurring_expenses_with_status)
        status_list = get_recurring_expenses_with_status(self.member, self.today)

        self.assertEqual(len(status_list), 1)
        self.assertEqual(status_list[0]["expense"], internet)
        self.assertEqual(status_list[0]["bank_account"], self.checking_account)
        self.assertEqual(status_list[0]["expected_amount"], Decimal("40.00"))
        self.assertEqual(status_list[0]["status"], RecurringExpenseStatus.WAITING)
