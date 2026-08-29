from typing import ClassVar

from django import forms

from budget.models import BankAccount, Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields: ClassVar[list[str]] = [
            "name",
            "type",
            "is_meal_voucher_eligible",
            "default_bank_account",
        ]

    def __init__(self, *args, household, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if "default_bank_account" in self.fields:
            self.fields["default_bank_account"].queryset = BankAccount.objects.filter(
                owner__household=household,
                is_active=True,
            )
