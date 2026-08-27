from typing import ClassVar

from django import forms

from budget.models.account import BankAccount


class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields: ClassVar[str] = [
            "name",
            "account_type",
            "current_balance",
            "visibility",
            "is_default",
            "daily_meal_voucher_limit",
            "fallback_account",
        ]

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)

        # On limite le compte relais aux autres comptes du même foyer
        if "fallback_account" in self.fields:
            self.fields["fallback_account"].queryset = BankAccount.objects.filter(
                owner__household=household,
                is_active=True,
            )
            # On empêche un compte d'être son propre relais en modification
            if self.instance and self.instance.pk:
                self.fields["fallback_account"].queryset = self.fields[
                    "fallback_account"
                ].queryset.exclude(pk=self.instance.pk)
