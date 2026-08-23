from django.contrib import admin
from django.urls import path

from budget.views import dashboard_view, quick_expense_form_view
from budget.views.dashboard import pay_recurring_expense_view
from budget.views.transactions import adjust_account_balance_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard_view, name="dashboard"),
    path("quick-expense/", quick_expense_form_view, name="quick_expense_form"),
    path(
        "account/<str:account_id>/adjust/",
        adjust_account_balance_view,
        name="adjust_account_balance",
    ),
    path(
        "recurring/<str:expense_id>/pay/",
        pay_recurring_expense_view,
        name="pay_recurring_expense",
    ),
]
