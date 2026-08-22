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
from budget.services.forecast import calculate_monthly_projected_balances


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
            name="Logement", default_bank_account=self.checking_account
        )
        self.cat_groceries = Category.objects.create(
            name="Courses",
            is_meal_voucher_eligible=True,
            default_bank_account=self.checking_account,
        )
        self.cat_salary = Category.objects.create(
            name="Salaire",
            is_income=True,
            default_bank_account=self.checking_account,
        )
        self.cat_savings = Category.objects.create(
            name="Épargne projet",
            default_bank_account=self.savings_account,
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
            steps["after_fixed"][self.checking_account.id], Decimal("900.00")
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
        )
        # Comme la transaction existe sur past_month, le réel a déjà impacté la banque.
        # after_fixed reste 920€ (pas de ré-imputation des 600€ théoriques).
        past_steps = calculate_monthly_projected_balances(
            member=self.member, month=past_month
        )
        self.assertEqual(
            past_steps["after_fixed"][self.checking_account.id], Decimal("920.00")
        )

        # 2. MOIS FUTUR : Aucune transaction sur septembre.
        # on déduit la prévision théorique (600€) du solde actuel (920€).
        # after_fixed = 920 - 600 = 320€
        future_steps = calculate_monthly_projected_balances(
            member=self.member, month=future_month
        )
        self.assertEqual(
            future_steps["after_fixed"][self.checking_account.id], Decimal("320.00")
        )

        # 3. MOIS EN COURS : Le loyer de 600€ est prélevé en août.
        # Solde BDD passe à 320€ (920 - 600).
        # La transaction existant pour août, after_fixed reste à 320€.
        Transaction.objects.create(
            transaction_date=current_month,
            budget_month=current_month,
            total_amount=Decimal("600.00"),
            category=self.cat_housing,
            bank_account=self.checking_account,
            transaction_type=TransactionType.EXPENSE,
        )
        current_steps = calculate_monthly_projected_balances(
            member=self.member, month=current_month
        )
        self.assertEqual(
            current_steps["after_fixed"][self.checking_account.id], Decimal("320.00")
        )
