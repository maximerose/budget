from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SoftDeleteModel


class Visibility(models.TextChoices):
    PRIVATE = "PRIVATE", "Privé"
    SHARED = "SHARED", "Partagé"


class Household(BaseModel, SoftDeleteModel):
    name = models.CharField(
        max_length=100,
        verbose_name="Nom du foyer",
        default="Mon foyer",
    )

    def __str__(self) -> str:
        return self.name

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = ("Foyer",)
        verbose_name_plural = "Foyers"


class HouseholdMember(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_user",
    )
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
        verbose_name="Foyer",
    )

    def __str__(self) -> str:
        if self.user:
            return f"{self.name} (@{self.user.username})"
        return self.name

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
    name = models.CharField(max_length=100, verbose_name="Nom du compte")
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.CHECKING,
        verbose_name="Type de compte",
    )
    owner = models.ForeignKey(
        HouseholdMember,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        verbose_name="Propriétaire du compte",
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.SHARED,
        verbose_name="Visibilité",
        help_text="Un compte privé ne sera visible que par son propriétaire.",
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.0"),
        verbose_name="Solde actuel",
    )
    daily_meal_voucher_limit = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Limite quotidienne de tickets resto",
        help_text="Si c'est un compte Tickets Resto, renseignez la limite quotidienne (ex : 25€)",
    )
    is_default = models.BooleanField(default=False, verbose_name="Compte par défaut")
    fallback_account = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fallback_for",
        verbose_name="Compte relais",
        help_text="Si ce compte est un compte Tickets Resto, alors vous pouvez renseigner un autre compte qui fait la bascule lors d'un paiement d'un montant supérieur à la limite quotidienne",
    )

    def __str__(self) -> str:
        account_type_label = AccountType(self.account_type).label
        owner_display = (
            f"(@{self.owner.user.username})" if self.owner.user else self.owner.name
        )
        return f"{self.name} ({account_type_label}) {owner_display}"

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
        verbose_name="Compte associé",
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Solde")
    date = models.DateField(default=timezone.localdate, verbose_name="Date")

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
