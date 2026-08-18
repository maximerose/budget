from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import BaseModel, SoftDeleteModel


class HouseholdMember(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100, null=False)
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


class Category(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100, null=False)
    is_meal_voucher_eligible = models.BooleanField(default=False)

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self) -> str:
        return self.name


class AccountType(models.TextChoices):
    CHECKING = "CHECKING", "Compte courant"
    SAVINGS = "SAVINGS", "Compte épargne"
    BUSINESS = "BUSINESS", "Compte pro"
    MEAL_VOUCHER = "MEAL_VOUCHER", "Tickets resto"
    OTHER = "OTHER", "Autre"


class BankAccount(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100, null=False)
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

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"

    def __str__(self) -> str:
        account_type_label = AccountType(self.account_type).label
        return f"{self.name} ({account_type_label})"
