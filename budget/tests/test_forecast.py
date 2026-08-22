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
    MonthlyForecastShare,
)


class MonthlyForecastTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.joint_account = BankAccount.objects.create(
            name="Compte joint",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("2000.00"),
        )
        self.checking_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )
        self.category = Category.objects.create(
            name="Courses", default_bank_account=self.joint_account
        )
        self.today = timezone.localdate().replace(day=1)

    def test_category_default_bank_account(self) -> None:
        self.assertEqual(self.category.default_bank_account, self.joint_account)

    def test_forecast_creation_and_remaining_amount(self) -> None:
        forecast = MonthlyForecast.objects.create(
            month=self.today,
            category=self.category,
            member=self.member,
            total_amount=Decimal("300.00"),
        )
        self.assertEqual(forecast.get_remaining_amount_to_split(), Decimal("300.00"))

        MonthlyForecastShare.objects.create(
            forecast=forecast,
            bank_account=self.category.default_bank_account,
            amount=Decimal("200.00"),
        )
        self.assertEqual(forecast.get_remaining_amount_to_split(), Decimal("100.00"))

    def test_share_validation_cannot_exceed_total_amount(self) -> None:
        forecast = MonthlyForecast.objects.create(
            month=self.today,
            category=self.category,
            member=self.member,
            total_amount=Decimal("300.00"),
        )
        MonthlyForecastShare.objects.create(
            forecast=forecast,
            bank_account=self.joint_account,
            amount=Decimal("200.00"),
        )

        invalid_share = MonthlyForecastShare(
            forecast=forecast,
            bank_account=self.checking_account,
            amount=Decimal("150.00"),
        )
        with self.assertRaises(ValidationError):
            invalid_share.full_clean()
