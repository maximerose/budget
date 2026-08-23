from decimal import Decimal
from urllib.request import Request

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from budget.models import BankAccount, HouseholdMember
from budget.models.recurring import RecurringExpense
from budget.services.forecast import (
    calculate_monthly_projected_balances,
    create_transaction_from_recurring_expense,
    get_recurring_expenses_with_status,
    get_target_account_for_expense,
)


def dashboard_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(is_active=True).first()
    accounts_with_projections = []
    recurring_expenses = []

    today = timezone.localdate().replace(day=1)

    if member:
        accounts = BankAccount.objects.filter(owner=member, is_active=True)
        recurring_expenses = get_recurring_expenses_with_status(member, today)
        projection_steps = calculate_monthly_projected_balances(member, today)

        # On associe les données de projection à chaque compte individuellement
        for account in accounts:
            accounts_with_projections.append(
                {
                    "account": account,
                    "totals": {
                        "initial": projection_steps.get("initial", {}).get(
                            account.id, Decimal("0.00")
                        ),
                        "after_fixed": projection_steps.get("after_fixed", {}).get(
                            account.id, Decimal("0.00")
                        ),
                        "after_variables": projection_steps.get(
                            "after_variables", {}
                        ).get(account.id, Decimal("0.00")),
                        "after_savings": projection_steps.get("after_savings", {}).get(
                            account.id, Decimal("0.00")
                        ),
                        "after_incomes": projection_steps.get("after_incomes", {}).get(
                            account.id, Decimal("0.00")
                        ),
                    },
                }
            )

    return render(
        request,
        "budget/dashboard.html",
        {
            "member": member,
            "accounts_data": accounts_with_projections,
            "recurring_expenses": recurring_expenses,
            "today": today,
        },
    )


def pay_recurring_expense_view(request: Request, expense_id: str) -> HttpResponse:
    expense = get_object_or_404(RecurringExpense, id=expense_id)
    member = HouseholdMember.objects.filter(is_active=True).first()

    # Récupération des comptes via la relation owner
    accounts = BankAccount.objects.filter(owner=member, is_active=True)

    # Compte par défaut initial si pas de POST
    target_account = get_target_account_for_expense(expense, member)

    if request.method == "POST":
        amount = Decimal(request.POST.get("amount", str(expense.total_amount)))
        account_id = request.POST.get("account_id")

        if account_id:
            target_account = get_object_or_404(
                BankAccount, id=account_id, owner=member, is_active=True
            )

        today = timezone.localdate()

        create_transaction_from_recurring_expense(
            expense=expense,
            bank_account=target_account,
            amount=amount,
            budget_month=today.replace(day=1),
        )

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return render(
        request,
        "budget/partials/recurring/_modal_pay_recurring.html",
        {
            "expense": expense,
            "account": target_account,
            "accounts": accounts,
        },
    )
