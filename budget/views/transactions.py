import datetime
import json
from decimal import Decimal
from urllib.request import Request

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from budget.models import (
    BankAccount,
    Category,
    HouseholdMember,
    Transaction,
    TransactionType,
)
from budget.models.account import AccountType, Visibility
from budget.models.category import CategoryType
from budget.models.transaction import Transfer
from budget.utils import (
    advance_date,
    calculate_budget_month,
    get_remaining_meal_voucher_ceiling,
    htmx_login_required,
)


@htmx_login_required
def adjust_account_balance_view(
    request: Request, account_id: str
) -> HttpResponse | None:
    account = get_object_or_404(BankAccount, id=account_id)

    if request.method == "POST":
        new_balance = Decimal(request.POST.get("new_balance", "0.00"))

        # On met à jour le solde du compte et la date
        account.current_balance = new_balance
        account.save()

        # On ferme la modale et on rafraîchit la page pour voir le nouveau solde
        response = HttpResponse("")
        response["HX-Refresh"] = "true"

        return response

    return render(
        request,
        "budget/partials/accounts/_modal_adjust_balance.html",
        {"account": account},
    )


@htmx_login_required
@require_http_methods(["GET", "POST"])
def quick_expense_form_view(request: Request) -> HttpResponse:
    current_member = HouseholdMember.objects.filter(
        user=request.user, is_active=True
    ).first()

    if request.method == "POST":
        tx_type = request.POST.get("tx_type", "EXPENSE")
        total_amount = Decimal(request.POST.get("total_amount", "0.00"))
        label = request.POST.get("label", "")
        transaction_date_str = request.POST.get("transaction_date")
        transaction_date = (
            datetime.date.fromisoformat(transaction_date_str)
            if transaction_date_str
            else timezone.localdate()
        )

        shift = int(request.POST.get("budget_shift", "0"))

        if shift != 0:
            target_date = advance_date(transaction_date, shift)
            budget_month = calculate_budget_month(
                transaction_date, target_date.year, target_date.month
            )
        else:
            budget_month = transaction_date

        if tx_type == "TRANSFER":
            Transfer.objects.create(
                source_account_id=request.POST.get("source_account"),
                destination_account_id=request.POST.get("destination_account"),
                amount=total_amount,
                date=transaction_date,
            )
        else:
            if tx_type == TransactionType.EXPENSE:
                category_id = request.POST.get("expense_category")
                bank_account_id = request.POST.get("expense_account")
                db_tx_type = TransactionType.EXPENSE
            else:
                category_id = request.POST.get("income_category")
                bank_account_id = request.POST.get("income_account")
                db_tx_type = TransactionType.INCOME

            meal_voucher_amount = Decimal(
                request.POST.get("meal_voucher_amount") or "0.00"
            )
            meal_voucher_account_id = request.POST.get("meal_voucher_account_id")

            Transaction.objects.create(
                total_amount=total_amount,
                label=label,
                category_id=category_id,
                bank_account_id=bank_account_id,
                transaction_date=transaction_date,
                budget_month=budget_month,
                transaction_type=db_tx_type,
                meal_voucher_amount=meal_voucher_amount
                if db_tx_type == TransactionType.EXPENSE
                else Decimal("0.00"),
                meal_voucher_bank_account_id=meal_voucher_account_id
                if meal_voucher_amount > 0 and db_tx_type == TransactionType.EXPENSE
                else None,
            )

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    # --- Préparation des listes pour le formulaire (GET) ---
    categories_expense = Category.objects.filter(
        is_active=True, household=current_member.household
    ).exclude(type__in=[CategoryType.INCOME, CategoryType.SAVINGS])

    categories_income = Category.objects.filter(
        is_active=True, household=current_member.household, type=CategoryType.INCOME
    ).exclude(type=CategoryType.SAVINGS)

    accounts = BankAccount.objects.filter(
        Q(owner=current_member)
        | Q(owner__household=current_member.household, visibility=Visibility.SHARED),
        is_active=True,
    ).distinct()

    default_account = accounts.filter(owner=current_member, is_default=True).first()
    selected_account_id = default_account.id if default_account else None

    account_options = [
        {
            "id": acc.id,
            "name": f"{acc.name} ({acc.owner.name})"
            if acc.owner_id != current_member.id
            else acc.name,
        }
        for acc in accounts
    ]

    today = timezone.localdate()

    tr_accounts = accounts.filter(account_type=AccountType.MEAL_VOUCHER)
    tr_accounts_info = []

    for tr in tr_accounts:
        rem = get_remaining_meal_voucher_ceiling(today, tr) or Decimal("0.00")
        tr_accounts_info.append(
            {
                "id": str(tr.id),
                "name": tr.name,
                "remaining": float(rem),
                "fallback_id": str(tr.fallback_account_id)
                if tr.fallback_account_id
                else "",
            }
        )

    cat_tr_map = {str(c.id): c.is_meal_voucher_eligible for c in categories_expense}

    return render(
        request,
        "budget/partials/transactions/_modal_quick_expense.html",
        {
            "categories_expense": categories_expense,
            "categories_income": categories_income,
            "accounts": account_options,
            "selected_account_id": selected_account_id,
            "today": today,
            "tr_accounts_info": tr_accounts_info,
            "tr_accounts_info_json": json.dumps(tr_accounts_info),
            "cat_tr_map": json.dumps(cat_tr_map),
        },
    )
