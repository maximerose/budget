from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    Category,
    HouseholdMember,
    MonthlyForecast,
)
from budget.models.account import Household
from budget.models.category import CategoryType


class MonthlyForecastTestCase(TestCase):
    def setUp(self) -> None:
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime", household=self.household
        )
        self.checking_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
        )
        self.category = Category.objects.create(
            name="Courses",
            type=CategoryType.VARIABLE,
            household=self.household,
        )
        self.today = timezone.localdate().replace(day=1)

    def test_forecast_creation_and_amount(self) -> None:
        """Vérifie la création simple d'une enveloppe budgétaire."""
        forecast = MonthlyForecast.objects.create(
            month=self.today,
            category=self.category,
            member=self.member,
            amount=Decimal("300.00"),
        )
        self.assertEqual(forecast.amount, Decimal("300.00"))

    def test_forecast_validation_rules(self) -> None:
        """Vérifie la contrainte d'exclusivité entre Catégorie et Compte bancaire."""
        # 1. Valide : Prévision sur une catégorie (Dépense / Revenu)
        forecast_cat = MonthlyForecast(
            month=self.today,
            member=self.member,
            category=self.category,
            amount=Decimal("300.00"),
        )
        forecast_cat.full_clean()

        # 2. Valide : Prévision sur un Compte Bancaire (Épargne)
        forecast_acc = MonthlyForecast(
            month=self.today,
            member=self.member,
            bank_account=self.checking_account,
            amount=Decimal("150.00"),
        )
        forecast_acc.full_clean()

        # 3. Invalide : Aucun des deux
        forecast_empty = MonthlyForecast(
            month=self.today, member=self.member, amount=Decimal("100.00")
        )
        with self.assertRaises(ValidationError):
            forecast_empty.full_clean()

        # 4. Invalide : Les deux renseignés
        forecast_both = MonthlyForecast(
            month=self.today,
            member=self.member,
            category=self.category,
            bank_account=self.checking_account,
            amount=Decimal("100.00"),
        )
        with self.assertRaises(ValidationError):
            forecast_both.full_clean()
