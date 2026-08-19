from django.core.exceptions import ValidationError
from django.db import models

from core.models import BaseModel, SoftDeleteModel


class Category(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    is_income = models.BooleanField(default=False)
    is_meal_voucher_eligible = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()

        # Règle métier : Un revenu ne peut pas être éligible aux Tickets Resto
        if self.is_income and self.is_meal_voucher_eligible:
            raise ValidationError(
                "Une catégorie de type revenu ne peut pas être éligible aux tickets resto"
            )

    def save(self, *args, **kwargs) -> None:
        # Force l'appel de clean() lors d'un .save() programmatique si besoin
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
