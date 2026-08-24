from django.contrib import admin

from budget.models import (
    AccountSnapshot,
    BankAccount,
    Category,
    HouseholdMember,
    MonthlyForecast,
    RecurringExpense,
    RecurringExpenseShare,
    Transaction,
    Transfer,
)
from budget.models.account import Household


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


admin.site.register(RecurringExpense)
admin.site.register(RecurringExpenseShare)
admin.site.register(MonthlyForecast)
admin.site.register(Transaction)
admin.site.register(Transfer)
admin.site.register(AccountSnapshot)
