from typing import ClassVar

from django import forms

from budget.models import BankAccount, Category, RecurringExpense
from budget.models.account import Household
from budget.models.category import CategoryType
from budget.models.recurring import RecurringExpenseShare


class RecurringExpenseForm(forms.ModelForm):
    class Meta:
        model = RecurringExpense
        fields: ClassVar[list[str]] = [
            "label",
            "total_amount",
            "category",
            "default_bank_account",
            "visibility",
            "is_variable",
            "frequency_months",
            "usual_due_day",
        ]

    def __init__(self, *args, household: Household, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Restreindre aux catégories "Récurrentes" du foyer
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(
                household=household,
                type=CategoryType.RECURRING,
                is_active=True,
            )

        # Restreindre aux comptes du foyer
        if "default_bank_account" in self.fields:
            self.fields["default_bank_account"].queryset = BankAccount.objects.filter(
                owner__household=household,
                is_active=True,
            )


class RecurringExpenseShareForm(forms.ModelForm):
    class Meta:
        model = RecurringExpenseShare
        fields: ClassVar[list[str]] = ["bank_account", "amount"]

    def __init__(self, *args, household: Household, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Rend le champ catégorie optionnel
        if "category" in self.fields:
            self.fields["category"].required = False
            self.fields["category"].queryset = Category.objects.filter(
                household=household,
                type=CategoryType.RECURRING,
                is_active=True,
            )

        # Restreindre aux comptes du foyer
        if "default_bank_account" in self.fields:
            self.fields["default_bank_account"].queryset = BankAccount.objects.filter(
                owner__household=household,
                is_active=True,
            )
