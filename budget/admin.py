from django.contrib import admin

from budget.models import (
    AccountSnapshot,
    BankAccount,
    Category,
    HouseholdMember,
    MonthlyForecast,
    MonthlyForecastShare,
    RecurringExpense,
    RecurringExpenseShare,
    Transaction,
    Transfer,
)


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


admin.site.register(RecurringExpense)
admin.site.register(RecurringExpenseShare)
admin.site.register(MonthlyForecast)
admin.site.register(MonthlyForecastShare)
admin.site.register(Transaction)
admin.site.register(Transfer)
admin.site.register(AccountSnapshot)
