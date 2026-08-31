from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from budget.models.account import AccountType, BankAccount, Household, HouseholdMember
from budget.models.category import Category, CategoryType
from budget.models.forecast import MonthlyForecast
from budget.models.transaction import Transaction, TransactionType
from core.models import Visibility

User = get_user_model()


class DashboardViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="maxime", password="password123")
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime",
            user=self.user,
            household=self.household,
        )
        self.client.force_login(self.user)

        self.account = BankAccount.objects.create(
            name="Compte Courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    # --- TESTS DU DASHBOARD PRINCIPAL ---

    def test_dashboard_view_with_active_member(self) -> None:
        """Vérifie que le dashboard charge correctement avec un membre actif."""
        url = reverse("dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "budget/dashboard.html")
        self.assertIn("member", response.context)
        self.assertEqual(response.context["member"], self.member)
        self.assertTrue(len(response.context["accounts_data"]) > 0)

    def test_dashboard_view_without_active_member(self) -> None:
        """Vérifie que le dashboard ne plante pas si aucun membre n'est actif."""
        # On désactive le seul membre existant
        self.member.is_active = False
        self.member.save()

        url = reverse("dashboard")
        response = self.client.get(url)

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)

    def test_dashboard_forecast_privacy_and_strict_realized_amounts(self) -> None:
        """Vérifie l'isolation des dépenses et la confidentialité des prévisions entre conjoints."""

        # Création de Laurie et de son compte partagé
        user_laurie = User.objects.create_user(
            username="laurie", password="password123"
        )
        member_laurie = HouseholdMember.objects.create(
            name="Laurie", household=self.household, user=user_laurie
        )

        account_laurie = BankAccount.objects.create(
            name="Compte Laurie",
            account_type=AccountType.CHECKING,
            owner=member_laurie,
            visibility=Visibility.SHARED,
        )

        cat_courses = Category.objects.create(
            name="Courses", type=CategoryType.VARIABLE, household=self.household
        )
        cat_cadeaux = Category.objects.create(
            name="Cadeaux", type=CategoryType.VARIABLE, household=self.household
        )

        today = timezone.localdate().replace(day=1)

        # Laurie fait une prévision PARTAGÉE de 200€ pour les courses
        MonthlyForecast.objects.create(
            month=today,
            category=cat_courses,
            member=member_laurie,
            amount=Decimal("200.00"),
            visibility=Visibility.SHARED,
        )

        # Laurie fait une prévision PRIVÉE de 100€ pour des cadeaux
        MonthlyForecast.objects.create(
            month=today,
            category=cat_cadeaux,
            member=member_laurie,
            amount=Decimal("100.00"),
            visibility=Visibility.PRIVATE,
        )

        # Maxime fait une prévision de 300€ pour les courses
        MonthlyForecast.objects.create(
            month=today,
            category=cat_courses,
            member=self.member,
            amount=Decimal("300.00"),
            visibility=Visibility.SHARED,
        )

        # Maxime dépense 55€ (Il est le "created_by")
        Transaction.objects.create(
            total_amount=Decimal("55.00"),
            category=cat_courses,
            bank_account=self.account,
            transaction_type=TransactionType.EXPENSE,
            created_by=self.user,
        )

        # Laurie dépense 35€ avec SON compte (Elle est le "created_by")
        Transaction.objects.create(
            total_amount=Decimal("35.00"),
            category=cat_courses,
            bank_account=account_laurie,
            transaction_type=TransactionType.EXPENSE,
            created_by=user_laurie,
        )

        # Maxime charge son dashboard
        response = self.client.get(reverse("dashboard"))

        # 1. Maxime ne doit voir que DEUX prévisions de charges variables (Celle de Laurie en privée est masquée)
        forecasts = response.context["variable_forecasts"]
        self.assertEqual(len(forecasts), 2)

        # 2. Vérification des montants réalisés stricts
        forecast_maxime = next(f for f in forecasts if f["member"] == self.member)
        forecast_laurie = next(f for f in forecasts if f["member"] == member_laurie)

        self.assertEqual(
            forecast_maxime["realized_amount"], Decimal("55.00")
        )  # Uniquement les 55 de Maxime
        self.assertEqual(
            forecast_laurie["realized_amount"], Decimal("35.00")
        )  # Uniquement les 35 de Laurie
