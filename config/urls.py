from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from budget.views import dashboard_view, quick_transaction_form_view
from budget.views.accounts import (
    settings_account_delete_view,
    settings_account_form_view,
    settings_accounts_list_view,
)
from budget.views.auth import join_household_view, register_view
from budget.views.categories import (
    settings_categories_list_view,
    settings_category_delete_view,
    settings_category_form_view,
    settings_category_merge_view,
)
from budget.views.dashboard import pay_recurring_expense_view
from budget.views.profile import (
    settings_generate_invite,
    settings_household_update,
    settings_profile_update,
    settings_profile_view,
)
from budget.views.recurring import (
    settings_recurring_delete_view,
    settings_recurring_form_view,
    settings_recurring_list_view,
    settings_recurring_share_delete_view,
    settings_recurring_shares_view,
)
from budget.views.transactions import (
    adjust_account_balance_view,
    monthly_history_view,
    transaction_delete_view,
    transaction_update_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Authentification ---
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", register_view, name="register"),
    path("join/<uuid:token>/", join_household_view, name="join_household"),
    # --- Application ---
    path("", dashboard_view, name="dashboard"),
    path(
        "quick-transaction/", quick_transaction_form_view, name="quick_transaction_form"
    ),
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
    path(
        "transactions/<uuid:transaction_id>/update/",
        transaction_update_view,
        name="transaction_update",
    ),
    path(
        "transactions/<uuid:transaction_id>/delete/",
        transaction_delete_view,
        name="transaction_delete",
    ),
    path(
        "transactions/history/",
        monthly_history_view,
        name="monthly_history",
    ),
    # --- Paramètres & Configuration ---
    path("settings/accounts/", settings_accounts_list_view, name="settings_accounts"),
    path(
        "settings/accounts/create/",
        settings_account_form_view,
        name="settings_account_create",
    ),
    path(
        "settings/accounts/<uuid:account_id>/update/",
        settings_account_form_view,
        name="settings_account_update",
    ),
    path(
        "settings/accounts/<uuid:account_id>/delete/",
        settings_account_delete_view,
        name="settings_account_delete",
    ),
    path(
        "settings/categories/",
        settings_categories_list_view,
        name="settings_categories",
    ),
    path(
        "settings/categories/create/",
        settings_category_form_view,
        name="settings_category_create",
    ),
    path(
        "settings/categories/<uuid:category_id>/update/",
        settings_category_form_view,
        name="settings_category_update",
    ),
    path(
        "settings/categories/<uuid:category_id>/delete/",
        settings_category_delete_view,
        name="settings_category_delete",
    ),
    path(
        "settings/categories/<uuid:category_id>/merge/",
        settings_category_merge_view,
        name="settings_category_merge",
    ),
    path(
        "settings/recurring/",
        settings_recurring_list_view,
        name="settings_recurring",
    ),
    path(
        "settings/recurring/create/",
        settings_recurring_form_view,
        name="settings_recurring_create",
    ),
    path(
        "settings/recurring/<uuid:expense_id>/update/",
        settings_recurring_form_view,
        name="settings_recurring_update",
    ),
    path(
        "settings/recurring/<uuid:expense_id>/delete/",
        settings_recurring_delete_view,
        name="settings_recurring_delete",
    ),
    path(
        "settings/recurring/<uuid:expense_id>/shares/",
        settings_recurring_shares_view,
        name="settings_recurring_shares",
    ),
    path(
        "settings/recurring/<uuid:expense_id>/shares/<uuid:share_id>/delete/",
        settings_recurring_share_delete_view,
        name="settings_recurring_share_delete",
    ),
    path("settings/profile/", settings_profile_view, name="settings_profile"),
    path(
        "settings/profile/update/",
        settings_profile_update,
        name="settings_profile_update",
    ),
    path(
        "settings/household/update/",
        settings_household_update,
        name="settings_household_update",
    ),
    path(
        "settings/household/invite/",
        settings_generate_invite,
        name="settings_generate_invite",
    ),
]
