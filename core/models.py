import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class BlameableModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True


class GlobalSettings(BaseModel):
    daily_meal_voucher_limit = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("25.00")
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Global Setting"
        verbose_name_plural = "Global Settings"

    def __str__(self) -> str:
        return f"Limite tickets resto / jour : {self.daily_meal_voucher_limit}€"
