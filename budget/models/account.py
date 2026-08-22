from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SoftDeleteModel


class HouseholdMember(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_user",
    )

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Membre du foyer"
        verbose_name_plural = "Membres du foyer"


class AccountType(models.TextChoices):
    CHECKING = "CHECKING", "Compte courant"
    SAVINGS = "SAVINGS", "Compte épargne"
    BUSINESS = "BUSINESS", "Compte pro"
    MEAL_VOUCHER = "MEAL_VOUCHER", "Tickets resto"
    OTHER = "OTHER", "Autre"


class BankAccount(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices, default=AccountType.CHECKING
    )
    owner = models.ForeignKey(
        HouseholdMember,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.0")
    )
    daily_meal_voucher_limit = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    def __str__(self) -> str:
        account_type_label = AccountType(self.account_type).label
        return f"{self.name} ({account_type_label})"

    def clean(self) -> None:
        super().clean()
        if self.account_type == AccountType.MEAL_VOUCHER:
            if not self.daily_meal_voucher_limit:
                self.daily_meal_voucher_limit = Decimal("25.00")
        else:
            self.daily_meal_voucher_limit = None

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"


class AccountSnapshot(BaseModel):
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(default=timezone.localdate)

    def __str__(self) -> str:
        return f"{self.bank_account.name} - {self.balance} € au {self.date}"

    class Meta(BaseModel.Meta):
        verbose_name = "Relevé de compte (Snapshot)"
        verbose_name_plural = "Relevés de comptes (Snapshots)"
        ordering: ClassVar[list[str]] = ["-date"]
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["bank_account", "date"], name="unique_daily_account_snapshot"
            )
        ]
