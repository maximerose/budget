from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

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


class Category(BaseModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    is_meal_voucher_eligible = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"


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

    def __str__(self) -> str:
        account_type_label = AccountType(self.account_type).label
        return f"{self.name} ({account_type_label})"

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"


class RecurringExpense(BaseModel, SoftDeleteModel):
    label = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    usual_due_day = models.DateField(null=True, blank=True)
    frequency_months = models.PositiveIntegerField(default=1)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="recurring_expenses"
    )

    def __str__(self) -> str:
        return f"{self.label} ({self.total_amount} €)"

    def get_remaining_amount_to_split(self) -> Decimal:
        """Calcule le montant qu'il reste à assigner parmi les parts."""
        allocated = self.shares.aggregate(models.Sum("amount"))[
            "amount__sum"
        ] or Decimal("0.00")
        return self.total_amount - allocated

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Charge récurrente"
        verbose_name_plural = "Charges récurrentes"


class RecurringExpenseShare(BaseModel, SoftDeleteModel):
    recurring_expense = models.ForeignKey(
        RecurringExpense, on_delete=models.CASCADE, related_name="shares"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="expense_shares"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self) -> str:
        return (
            f"{self.recurring_expense.label} - {self.bank_account.name}: {self.amount}€"
        )

    def clean(self) -> None:
        super().clean()
        if not self.recurring_expense.id:
            return

        existing_shares_sum = RecurringExpenseShare.objects.filter(
            recurring_expense=self.recurring_expense
        ).exclude(pk=self.pk).aggregate(models.Sum("amount"))["amount__sum"] or Decimal(
            "0.00"
        )

        total_with_this_share = existing_shares_sum + self.amount

        if total_with_this_share > self.recurring_expense.total_amount:
            raise ValidationError(
                f"La somme des parts ({total_with_this_share} €) dépasse le montant total de la charge ({self.recurring_expense.total_amount} €)."
            )

    class Meta(BaseModel.Meta, SoftDeleteModel.Meta):
        verbose_name = "Répartition de dépense"
        verbose_name_plural = "Répartitions de dépenses"
