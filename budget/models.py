from django.conf import settings
from django.db import models

from core.models import BaseModel, BlameableModel, SoftDeleteModel


class HouseholdMember(BaseModel, SoftDeleteModel, BlameableModel):
    name = models.CharField(max_length=100, null=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_user",
    )

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta, BlameableModel.Meta):
        verbose_name = "Membre du foyer"
        verbose_name_plural = "Membres du foyer"
