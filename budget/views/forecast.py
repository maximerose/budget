import datetime
from decimal import Decimal, DecimalException
from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from budget.models import (
    BankAccount,
    Category,
    MonthlyForecast,
    RecurringExpense,
)
from budget.models.account import AccountType
from budget.models.category import CategoryType


@login_required
def forecast_list_view(request: Request) -> HttpResponse:
    member = request.member
    household = request.household

    month_str = request.GET.get("month")
    selected_date = timezone.localdate().replace(day=1)

    if month_str:
        try:
            selected_date = datetime.date.fromisoformat(f"{month_str}-01")
        except ValueError:
            pass

    # 1. Sauvegarde des prévisions (POST)
    if request.method == "POST":
        action = request.POST.get("action", "save")

        with transaction.atomic():
            if action == "save":
                for key, value in request.POST.items():
                    # On ignore les champs système comme csrfmiddlewaretoken et action
                    if not (
                        key.startswith(
                            ("forecast_cat_", "forecast_acc_", "forecast_rec_")
                        )
                    ):
                        continue

                    if not value.strip():
                        continue

                    try:
                        amount = Decimal(value.replace(",", "."))
                    except (ValueError, TypeError, DecimalException):
                        continue

                    # Option A : Catégorie (Variable ou Revenu)
                    if key.startswith("forecast_cat_"):
                        cat_id = key.replace("forecast_cat_", "")
                        MonthlyForecast.objects.update_or_create(
                            month=selected_date,
                            member=member,
                            category_id=cat_id,
                            defaults={"amount": amount},
                        )

                    # Option B : Compte Épargne
                    elif key.startswith("forecast_acc_"):
                        acc_id = key.replace("forecast_acc_", "")
                        MonthlyForecast.objects.update_or_create(
                            month=selected_date,
                            member=member,
                            bank_account_id=acc_id,
                            defaults={"amount": amount},
                        )

                    # Option C : Override Charge Fixe
                    elif key.startswith("forecast_rec_"):
                        rec_id = key.replace("forecast_rec_", "")
                        MonthlyForecast.objects.update_or_create(
                            month=selected_date,
                            member=member,
                            recurring_expense_id=rec_id,
                            defaults={"amount": amount},
                        )

            elif action == "replicate":
                try:
                    months_count = int(request.POST.get("replicate_months", 1))
                except ValueError:
                    months_count = 1

                current_forecasts = MonthlyForecast.objects.filter(
                    member__household=household,
                    month=selected_date,
                    is_active=True,
                )

                for i in range(1, months_count + 1):
                    month_offset = selected_date.month - 1 + i
                    new_year = selected_date.year + month_offset // 12
                    new_month = month_offset % 12 + 1
                    target_month = datetime.date(new_year, new_month, 1)

                    for f in current_forecasts:
                        MonthlyForecast.objects.update_or_create(
                            month=target_month,
                            member=f.member,
                            category=f.category,
                            bank_account=f.bank_account,
                            recurring_expense=f.recurring_expense,
                            defaults={"amount": f.amount, "visibility": f.visibility},
                        )

        return redirect(f"{request.path}?month={selected_date.strftime('%Y-%m')}")

    # 2. Chargement des données existantes
    existing_forecasts = MonthlyForecast.objects.filter(
        member__household=household, month=selected_date, is_active=True
    )

    cat_map = {f.category_id: f.amount for f in existing_forecasts if f.category_id}
    acc_map = {
        f.bank_account_id: f.amount for f in existing_forecasts if f.bank_account_id
    }
    rec_map = {
        f.recurring_expense_id: f.amount
        for f in existing_forecasts
        if f.recurring_expense_id
    }

    # --- SECTION 1 : Catégories Variables ---
    var_categories = Category.objects.filter(
        household=household, type=CategoryType.VARIABLE, is_active=True
    )
    var_data = [
        {"id": c.id, "name": c.name, "amount": cat_map.get(c.id, Decimal("0.00"))}
        for c in var_categories
    ]

    # --- SECTION 2 : Charges Fixes ---
    recurring_items = RecurringExpense.objects.filter(
        household=household, is_active=True
    )
    fix_data = []
    for r in recurring_items:
        allocated = rec_map.get(r.id, r.total_amount)
        fix_data.append(
            {
                "id": r.id,
                "name": r.label,
                "amount": allocated,
                "default_amount": r.total_amount,
            }
        )

    # --- SECTION 3 : Épargne ---
    savings_accounts = BankAccount.objects.filter(
        owner__household=household,
        account_type=AccountType.SAVINGS,
        is_active=True,
    )
    savings_data = [
        {"id": a.id, "name": a.name, "amount": acc_map.get(a.id, Decimal("0.00"))}
        for a in savings_accounts
    ]

    # --- SECTION 4 : Revenus ---
    income_categories = Category.objects.filter(
        household=household, type=CategoryType.INCOME, is_active=True
    )
    income_data = [
        {"id": c.id, "name": c.name, "amount": cat_map.get(c.id, Decimal("0.00"))}
        for c in income_categories
    ]

    return render(
        request,
        "budget/forecast/forecast_list.html",
        {
            "selected_month": selected_date,
            "var_data": var_data,
            "fix_data": fix_data,
            "savings_data": savings_data,
            "income_data": income_data,
            "breadcrumbs": ["Prévisions budgétaires"],
        },
    )
