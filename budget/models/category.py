from django.db import models

from core.models import BaseModel, SoftDeleteModel


class Category(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    is_meal_voucher_eligible = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
