from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SoftDeleteModel

from .account import BankAccount, HouseholdMember
from .category import Category


class MonthlyForecast(BaseModel, SoftDeleteModel):
    month = models.DateField(
        default=timezone.localdate,
        verbose_name="Mois",
    )
    member = models.ForeignKey(
        HouseholdMember,
        on_delete=models.CASCADE,
        related_name="forecasts",
        verbose_name="Utilisateur associé",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Montant de la prévision",
    )

    # Option A : Pour les dépenses et les revenus
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="forecasts",
        null=True,
        blank=True,
        verbose_name="Catégorie (Dépenses / Revenus)",
    )

    # Option B : Pour l'épargne
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="savings_forecasts",
        null=True,
        blank=True,
        verbose_name="Compte cible (Épargne)",
    )

    def __str__(self) -> str:
        return f"{self.member.name} - {self.category.name} ({self.month.strftime('%m/%Y')}): {self.amount} €"

    def clean(self) -> None:
        super().clean()
        if not self.category and not self.bank_account:
            raise ValidationError(
                "Une prévision doit être liée soit à une Catégorie, soit à un Compte bancaire."
            )
        if self.category and self.bank_account:
            raise ValidationError(
                "Une prévision ne peut pas être liée à la fois à une Catégorie et à un Compte bancaire."
            )

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Prévision mensuelle"
        verbose_name_plural = "Prévisions mensuelles"
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["month", "category", "member"],
                name="unique_monthly_category_forecast_per_member",
            )
        ]
