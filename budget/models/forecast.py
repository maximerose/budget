from decimal import Decimal
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import BaseModel, SoftDeleteModel

from .account import BankAccount, HouseholdMember
from .category import Category


class MonthlyForecast(BaseModel, SoftDeleteModel):
    month = models.DateField(default=timezone.localdate)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="forecasts"
    )
    member = models.ForeignKey(
        HouseholdMember, on_delete=models.CASCADE, related_name="forecasts"
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.member.name} - {self.category.name} ({self.month.strftime('%m/%Y')}): {self.total_amount} €"

    def get_remaining_amount_to_split(self) -> Decimal:
        """Calcule le montant restant à répartir entre les comptes."""
        allocated = self.shares.aggregate(models.Sum("amount"))[
            "amount__sum"
        ] or Decimal("0.00")
        return self.total_amount - allocated

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Prévision mensuelle"
        verbose_name_plural = "Prévisions mensuelles"
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["month", "category", "member"],
                name="unique_monthly_category_forecast_per_member",
            )
        ]


class MonthlyForecastShare(BaseModel, SoftDeleteModel):
    forecast = models.ForeignKey(
        MonthlyForecast, on_delete=models.CASCADE, related_name="shares"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="forecast_shares"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self) -> str:
        return (
            f"{self.forecast.category.name} - {self.bank_account.name}: {self.amount} €"
        )

    def clean(self) -> None:
        super().clean()
        if not self.forecast_id:
            return

        existing_shares_sum = MonthlyForecastShare.objects.filter(
            forecast=self.forecast
        ).exclude(pk=self.pk).aggregate(models.Sum("amount"))["amount__sum"] or Decimal(
            "0.00"
        )

        if existing_shares_sum + self.amount > self.forecast.total_amount:
            raise ValidationError(
                f"La somme des parts ({existing_shares_sum + self.amount} €) dépasse le montant total de la prévision ({self.forecast.total_amount} €)."
            )

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Répartition de prévision"
        verbose_name_plural = "Répartitions de prévisions"
