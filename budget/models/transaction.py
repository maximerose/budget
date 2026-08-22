from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import BaseModel

from .account import BankAccount
from .category import Category


class TransactionType(models.TextChoices):
    INCOME = "INCOME", "Revenu"
    EXPENSE = "EXPENSE", "Dépense"


class Transaction(BaseModel):
    transaction_date = models.DateField(default=timezone.localdate)
    transaction_type = models.CharField(
        max_length=20, choices=TransactionType.choices, default=TransactionType.EXPENSE
    )
    budget_month = models.DateField(default=timezone.localdate)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    meal_voucher_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    label = models.CharField(max_length=100, blank=True, default="")
    comment = models.CharField(max_length=255, blank=True, default="")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="transactions"
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    recurring_expense = models.ForeignKey(
        "budget.RecurringExpense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    meal_voucher_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_voucher_transactions",
    )

    def __str__(self) -> str:
        sign = "+" if self.transaction_type == TransactionType.INCOME else "-"
        return f"[{self.get_transaction_type_display()}] {self.transaction_date} - {self.category.name}: {sign}{self.total_amount} € ({self.label})"

    def save(self, *args, **kwargs) -> None:
        is_new = self._state.adding

        # Si la transaction existe déjà, on doit d'abord restaurer les anciens soldes
        # pour éviter de fausser les comptes lors d'une modification.
        if not is_new:
            old_self = Transaction.objects.get(pk=self.pk)
            # Restauration ancien compte principal
            old_self.bank_account.current_balance += (
                old_self.total_amount - old_self.meal_voucher_amount
            )
            old_self.bank_account.save(update_fields=["current_balance"])
            # Restauration ancien compte TR si présent
            if (
                old_self.meal_voucher_amount > 0
                and hasattr(old_self, "meal_voucher_bank_account")
                and old_self.meal_voucher_bank_account
            ):
                old_self.meal_voucher_bank_account.current_balance += (
                    old_self.meal_voucher_amount
                )
                old_self.meal_voucher_bank_account.save(
                    update_fields=["current_balance"]
                )

        super().save(*args, **kwargs)

        # Application des nouveaux débits sur les comptes
        if self.transaction_type == TransactionType.EXPENSE:
            # Débit du compte principal (Total - TR)
            cash_amount = self.total_amount - self.meal_voucher_amount
            self.bank_account.current_balance -= cash_amount
            self.bank_account.save(update_fields=["current_balance"])

            # Débit du compte TR si un montant TR et un compte TR sont associés
            if (
                self.meal_voucher_amount > 0
                and hasattr(self, "meal_voucher_bank_account")
                and self.meal_voucher_bank_account
            ):
                self.meal_voucher_bank_account.current_balance -= (
                    self.meal_voucher_amount
                )
                self.meal_voucher_bank_account.save(update_fields=["current_balance"])

    class Meta(BaseModel.Meta):
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"


class Transfer(BaseModel):
    source_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="transfers_sent",
    )
    destination_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="transfers_received",
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField(default=timezone.localdate)

    def __str__(self) -> str:
        return f"Transfert de {self.amount} € ({self.source_account.name} -> {self.destination_account.name})"

    def clean(self) -> None:
        super().clean()

        if (
            self.source_account_id
            and self.source_account_id == self.destination_account_id
        ):
            raise ValidationError(
                "Le compte source et le compte destination doivent être différents."
            )

    def save(self, *args, **kwargs) -> None:
        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new:
            # Débiter le compte source
            self.source_account.current_balance -= self.amount
            self.source_account.save(update_fields=["current_balance"])

            # Créditer le compte destination
            self.destination_account.current_balance += self.amount
            self.destination_account.save(update_fields=["current_balance"])

    class Meta(BaseModel.Meta):
        verbose_name = "Transfert"
        verbose_name_plural = "Transferts"
