from decimal import Decimal
from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.aggregates import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from budget.models import BankAccount, HouseholdMember
from budget.models.account import AccountType
from budget.models.category import CategoryType
from budget.models.forecast import MonthlyForecast
from budget.models.recurring import RecurringExpense
from budget.models.transaction import Transaction, TransactionType, Transfer
from budget.services.forecast import (
    calculate_monthly_projected_balances,
    create_transaction_from_recurring_expense,
    get_recurring_expenses_with_status,
    get_target_account_for_expense,
)
from budget.utils import get_target_month_from_request, htmx_login_required
from core.models import Visibility


@login_required
def dashboard_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    if not member:
        return redirect("/login/")

    accounts_with_projections = []
    recurring_expenses = []
    recent_transactions = []
    variable_forecasts = []
    savings_forecasts = []

    today = get_target_month_from_request(request)

    if member:
        household = member.household
        accounts = BankAccount.objects.filter(
            Q(owner=member)
            | Q(owner__household=household, visibility=Visibility.SHARED),
            is_active=True,
        ).distinct()

        # 1. 10 Dernières transactions (Dépenses, Revenus, TR)
        recent_transactions = Transaction.objects.filter(
            bank_account__in=accounts,
            budget_month__year=today.year,
            budget_month__month=today.month,
        ).select_related(
            "category",
            "bank_account",
            "bank_account__owner",
            "meal_voucher_bank_account",
        )[:10]

        # 2. Charges fixes
        recurring_expenses = get_recurring_expenses_with_status(member, today)

        # 3. Enveloppes des charges variables restantes par catégorie
        category_forecasts = MonthlyForecast.objects.filter(
            Q(member=member) | Q(visibility=Visibility.SHARED),
            member__household=household,
            month__year=today.year,
            month__month=today.month,
            category__isnull=False,
            category__type=CategoryType.VARIABLE,
            is_active=True,
        ).select_related("category", "member")

        for forecast in category_forecasts:
            category = forecast.category
            realized = Transaction.objects.filter(
                bank_account__owner=forecast.member,
                bank_account__in=accounts,
                category=category,
                recurring_expense__isnull=True,
                budget_month__year=today.year,
                budget_month__month=today.month,
                transaction_type=TransactionType.EXPENSE,
            ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

            remaining = max(Decimal("0.00"), forecast.amount - realized)
            variable_forecasts.append(
                {
                    "category": category,
                    "member": forecast.member,
                    "budget_amount": forecast.amount,
                    "realized_amount": realized,
                    "remaining_amount": remaining,
                }
            )

        # 4. Enveloppes d'épargne restantes
        savings_qs = MonthlyForecast.objects.filter(
            Q(member=member) | Q(visibility=Visibility.SHARED),
            member__household=household,
            month__year=today.year,
            month__month=today.month,
            bank_account__isnull=False,
            bank_account__account_type=AccountType.SAVINGS,
            is_active=True,
        ).select_related("bank_account", "member")

        for forecast in savings_qs:
            target_account = forecast.bank_account
            realized_transfers = Transfer.objects.filter(
                source_account__owner=forecast.member,
                destination_account=target_account,
                source_account__in=accounts,
                date__year=today.year,
                date__month=today.month,
            ).aggregate(Sum("amount"))["amount__sum"] or Decimal("0.00")

            realized_tx = Transaction.objects.filter(
                budget_month__year=today.year,
                budget_month__month=today.month,
                bank_account=target_account,
                transaction_type=TransactionType.INCOME,
            ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

            realized = realized_transfers + realized_tx
            remaining = max(Decimal("0.00"), forecast.amount - realized)

            # On append bien dans la liste, et non dans le queryset
            savings_forecasts.append(
                {
                    "account": target_account,
                    "member": forecast.member,
                    "budget_amount": forecast.amount,
                    "realized_amount": realized,
                    "remaining_amount": remaining,
                }
            )

        # 5. Calcul des prévisions
        projection_steps = calculate_monthly_projected_balances(member, today)
        for account in accounts:
            accounts_with_projections.append(
                {
                    "account": account,
                    "totals": {
                        "initial": round(
                            projection_steps.get("initial", {}).get(
                                account.id, Decimal("0.00")
                            ),
                            2,
                        ),
                        "after_recurring": round(
                            projection_steps.get("after_recurring", {}).get(
                                account.id, Decimal("0.00")
                            ),
                            2,
                        ),
                        "after_variables": round(
                            projection_steps.get("after_variables", {}).get(
                                account.id, Decimal("0.00")
                            ),
                            2,
                        ),
                        "after_savings": round(
                            projection_steps.get("after_savings", {}).get(
                                account.id, Decimal("0.00")
                            ),
                            2,
                        ),
                        "after_incomes": round(
                            projection_steps.get("after_incomes", {}).get(
                                account.id, Decimal("0.00")
                            ),
                            2,
                        ),
                    },
                }
            )

    return render(
        request,
        "budget/dashboard.html",
        {
            "member": member,
            "recent_transactions": recent_transactions,
            "recurring_expenses": recurring_expenses,
            "variable_forecasts": variable_forecasts,
            "savings_forecasts": savings_forecasts,
            "accounts_data": accounts_with_projections,
            "today": today,
        },
    )


@htmx_login_required
def pay_recurring_expense_view(request: Request, expense_id: str) -> HttpResponse:
    expense = get_object_or_404(RecurringExpense, id=expense_id)
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    today = timezone.localdate()

    # Récupération des comptes via la relation owner
    accounts = BankAccount.objects.filter(
        Q(owner=member)
        | Q(owner__household=member.household, visibility=Visibility.SHARED),
        is_active=True,
        account_type__in=[AccountType.CHECKING, AccountType.BUSINESS],
    ).distinct()

    # 1. FORMATAGE DU SELECT : On ajoute le nom du propriétaire si ce n'est pas le nôtre
    account_options = [
        {
            "id": acc.id,
            "name": f"{acc.name} ({acc.owner.name})"
            if acc.owner_id != member.id
            else acc.name,
        }
        for acc in accounts
    ]

    # Compte par défaut initial si pas de POST
    target_account = get_target_account_for_expense(expense, member)

    # 2. DÉTECTION DU MONTANT À PAYER (Exception du mois + Quote-part)
    override = MonthlyForecast.objects.filter(
        member__household=member.household,
        month__year=today.year,
        month__month=today.month,
        recurring_expense=expense,
        is_active=True,
    ).first()

    expected_total = override.amount if override else expense.total_amount
    amount_to_pay = expected_total

    realized_total = Transaction.objects.filter(
        recurring_expense=expense,
        budget_month__year=today.year,
        budget_month__month=today.month,
        transaction_type=TransactionType.EXPENSE,
    ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

    remaining_to_pay = max(Decimal("0.00"), expected_total - realized_total)

    shares = expense.shares.filter(is_active=True)
    shares_details = []

    if shares.exists():
        for share in shares:
            ratio = (
                share.amount / expense.total_amount
                if expense.total_amount > Decimal("0.00")
                else Decimal("1.00")
            )
            prorated = round(expected_total * ratio, 2)
            owner_name = (
                share.bank_account.owner.name if share.bank_account.owner else "Foyer"
            )
            shares_details.append({"name": owner_name, "amount": prorated})

        # Si la charge est divisée, on cherche la part du membre connecté
        member_share = shares.filter(bank_account__in=accounts).first()
        if member_share:
            ratio = (
                member_share.amount / expense.total_amount
                if expense.total_amount > Decimal("0.00")
                else Decimal("1.00")
            )
            amount_to_pay = round(expected_total * ratio, 2)
            target_account = member_share.bank_account

    if request.method == "POST":
        amount = Decimal(request.POST.get("amount", str(amount_to_pay)))
        account_id = request.POST.get("account_id")
        update_default = request.POST.get("update_default") == "on"

        if account_id:
            target_account = get_object_or_404(
                BankAccount,
                id=account_id,
                owner=member,
                is_active=True,
            )

        create_transaction_from_recurring_expense(
            expense=expense,
            bank_account=target_account,
            amount=amount,
            budget_month=today.replace(day=1),
        )

        # Si l'utilisateur a coché "Appliquer définitivement"
        if update_default:
            if shares.exists():
                member_share = shares.filter(bank_account__in=accounts).first()
                if member_share:
                    # On ajuste la part du membre et on répercute la différence sur le total global de la charge
                    diff = amount - member_share.amount
                    member_share.amount = amount
                    member_share.save()

                    expense.total_amount += diff
                    expense.save()
            else:
                # Si pas de partage, on met à jour le montant brut de la charge
                expense.total_amount = amount
                expense.save()

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return render(
        request,
        "budget/partials/recurring/_modal_pay_recurring.html",
        {
            "expense": expense,
            "account": target_account,
            "accounts": account_options,
            "amount_to_pay": amount_to_pay,
            "expected_total": expected_total,
            "remaining_to_pay": remaining_to_pay,
            "shares_details": shares_details,
        },
    )
