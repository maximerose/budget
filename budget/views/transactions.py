import datetime
import json
from decimal import Decimal
from urllib.request import Request

from django.contrib import messages
from django.db.models import Q
from django.db.models.aggregates import Min
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from budget.models import (
    BankAccount,
    Category,
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

        account.current_balance = new_balance
        account.save()

        messages.success(request, "Solde ajusté")

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
def quick_transaction_form_view(request: Request) -> HttpResponse:
    current_member = request.member
    household = request.household

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
            source_id = request.POST.get("source_account")
            dest_id = request.POST.get("destination_account")
            transfer_category_id = request.POST.get("transfer_category")

            if transfer_category_id:
                # Remboursement "Catégorisé"
                Transaction.objects.create(
                    total_amount=total_amount,
                    label=label or "Remboursement envoyé",
                    category_id=transfer_category_id,
                    bank_account_id=source_id,
                    transaction_date=transaction_date,
                    budget_month=budget_month,
                    transaction_type=TransactionType.EXPENSE,
                )
                Transaction.objects.create(
                    total_amount=-total_amount,
                    label=label or "Remboursement reçu",
                    category_id=transfer_category_id,
                    bank_account_id=dest_id,
                    transaction_date=transaction_date,
                    budget_month=budget_month,
                    transaction_type=TransactionType.EXPENSE,
                )
            else:
                # Transfert simple
                Transfer.objects.create(
                    source_account_id=source_id,
                    destination_account_id=dest_id,
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

        messages.success(request, "Dépense ajoutée")

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    # --- GET ---
    categories_expense = list(
        Category.objects.filter(is_active=True, household=household)
        .exclude(type__in=[CategoryType.INCOME, CategoryType.SAVINGS])
        .only("id", "name", "is_meal_voucher_eligible")
    )

    categories_income = list(
        Category.objects.filter(
            is_active=True, household=household, type=CategoryType.INCOME
        )
        .exclude(type=CategoryType.SAVINGS)
        .only("id", "name")
    )

    accounts = list(
        BankAccount.objects.filter(
            Q(owner=current_member)
            | Q(owner__household=household, visibility=Visibility.SHARED),
            is_active=True,
        )
        .select_related("owner")
        .distinct()
    )

    default_account = next(
        (
            acc
            for acc in accounts
            if acc.owner_id == current_member.id and acc.is_default
        ),
        None,
    )
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

    tr_accounts = [
        acc for acc in accounts if acc.account_type == AccountType.MEAL_VOUCHER
    ]
    tr_accounts_info = []

    if tr_accounts:
        # Récupération en une seule requête plate sans subqueries complexes
        today_txs = list(
            Transaction.objects.filter(
                transaction_date=today,
                transaction_type=TransactionType.EXPENSE,
            ).only(
                "bank_account_id",
                "meal_voucher_bank_account_id",
                "total_amount",
                "meal_voucher_amount",
            )
        )

        for tr in tr_accounts:
            limit = tr.daily_meal_voucher_limit or Decimal("25.00")

            spent_as_tr = sum(
                tx.meal_voucher_amount
                for tx in today_txs
                if tx.meal_voucher_bank_account_id == tr.id
            )
            spent_as_main = sum(
                (tx.total_amount - tx.meal_voucher_amount)
                for tx in today_txs
                if tx.bank_account_id == tr.id
            )

            remaining = max(Decimal("0.00"), limit - (spent_as_tr + spent_as_main))

            tr_accounts_info.append(
                {
                    "id": str(tr.id),
                    "name": tr.name,
                    "remaining": float(remaining),
                    "fallback_id": str(tr.fallback_account_id)
                    if tr.fallback_account_id
                    else "",
                }
            )

    cat_tr_map = {str(c.id): c.is_meal_voucher_eligible for c in categories_expense}

    return render(
        request,
        "budget/partials/transactions/_modal_quick_transaction.html",
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


@htmx_login_required
@require_http_methods(["GET", "POST"])
def transaction_update_view(request: Request, transaction_id: str) -> HttpResponse:
    current_member = request.member
    household = request.household

    tx = get_object_or_404(
        Transaction,
        id=transaction_id,
        bank_account__owner=current_member,
    )

    if request.method == "POST":
        tx_type = request.POST.get("tx_type", "EXPENSE")
        total_amount = Decimal(request.POST.get("total_amount", "0.00"))
        label = request.POST.get("label", "")
        transaction_date_str = request.POST.get("transaction_date")
        transaction_date = (
            datetime.date.fromisoformat(transaction_date_str)
            if transaction_date_str
            else tx.transaction_date
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
            source_id = request.POST.get("source_account")
            dest_id = request.POST.get("destination_account")
            transfer_category_id = request.POST.get("transfer_category")

            tx.delete()

            if transfer_category_id:
                Transaction.objects.create(
                    total_amount=total_amount,
                    label=label or "Remboursement envoyé",
                    category_id=transfer_category_id,
                    bank_account_id=source_id,
                    transaction_date=transaction_date,
                    budget_month=budget_month,
                    transaction_type=TransactionType.EXPENSE,
                )
                Transaction.objects.create(
                    total_amount=-total_amount,
                    label=label or "Remboursement reçu",
                    category_id=transfer_category_id,
                    bank_account_id=dest_id,
                    transaction_date=transaction_date,
                    budget_month=budget_month,
                    transaction_type=TransactionType.EXPENSE,
                )
            else:
                Transfer.objects.create(
                    source_account_id=source_id,
                    destination_account_id=dest_id,
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

            tx.transaction_type = db_tx_type
            tx.total_amount = total_amount
            tx.label = label
            tx.category_id = category_id
            tx.bank_account_id = bank_account_id
            tx.transaction_date = transaction_date
            tx.budget_month = budget_month
            tx.meal_voucher_amount = (
                meal_voucher_amount
                if db_tx_type == TransactionType.EXPENSE
                else Decimal("0.00")
            )
            tx.meal_voucher_bank_account_id = (
                meal_voucher_account_id
                if meal_voucher_amount > 0 and db_tx_type == TransactionType.EXPENSE
                else None
            )

            tx.save()

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    categories_expense = Category.objects.filter(
        is_active=True, household=household
    ).exclude(type__in=[CategoryType.INCOME, CategoryType.SAVINGS])

    categories_income = Category.objects.filter(
        is_active=True, household=household, type=CategoryType.INCOME
    ).exclude(type=CategoryType.SAVINGS)

    accounts = (
        BankAccount.objects.filter(
            Q(owner=current_member)
            | Q(owner__household=household, visibility=Visibility.SHARED),
            is_active=True,
        )
        .select_related("owner")
        .distinct()
    )

    account_options = [
        {
            "id": acc.id,
            "name": f"{acc.name} ({acc.owner.name})"
            if acc.owner_id != current_member.id
            else acc.name,
        }
        for acc in accounts
    ]

    tr_accounts = [
        acc for acc in accounts if acc.account_type == AccountType.MEAL_VOUCHER
    ]
    tr_accounts_info = [
        {
            "id": str(tr.id),
            "name": tr.name,
            "remaining": float(
                get_remaining_meal_voucher_ceiling(
                    tx.transaction_date, tr, exclude_transaction_pk=tx.pk
                )
                or Decimal("0.00")
            ),
            "fallback_id": str(tr.fallback_account_id)
            if tr.fallback_account_id
            else "",
        }
        for tr in tr_accounts
    ]

    cat_tr_map = {str(c.id): c.is_meal_voucher_eligible for c in categories_expense}

    shift = 0
    if tx.budget_month and tx.transaction_date:
        tx_m = (tx.transaction_date.year, tx.transaction_date.month)
        bg_m = (tx.budget_month.year, tx.budget_month.month)

        if bg_m < tx_m:
            shift = -1
        elif bg_m > tx_m:
            shift = 1

    return render(
        request,
        "budget/partials/transactions/_modal_quick_transaction.html",
        {
            "transaction": tx,
            "budget_shift": shift,
            "selected_category_id": tx.category_id,
            "categories_expense": categories_expense,
            "categories_income": categories_income,
            "accounts": account_options,
            "selected_account_id": tx.bank_account_id,
            "today": tx.transaction_date,
            "tr_accounts_info": tr_accounts_info,
            "tr_accounts_info_json": json.dumps(tr_accounts_info),
            "cat_tr_map": json.dumps(cat_tr_map),
        },
    )


@htmx_login_required
def transaction_delete_view(request: Request, transaction_id: str) -> HttpResponse:
    member = request.member
    tx = get_object_or_404(
        Transaction,
        id=transaction_id,
        bank_account__owner=member,
    )

    if request.method == "POST":
        tx.delete()
        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)


@htmx_login_required
def monthly_history_view(request: Request) -> HttpResponse:
    household = request.household
    today = timezone.localdate().replace(day=1)

    # 1. Bornes globales
    min_tx_date = Transaction.objects.filter(
        bank_account__owner__household=household
    ).aggregate(m=Min("budget_month"))["m"]

    start_boundary = min_tx_date.replace(day=1) if min_tx_date else today
    end_boundary = today

    # 2. Récupération des filtres de dates
    start_str = request.GET.get("start_month")
    end_str = request.GET.get("end_month")

    try:
        start_date = (
            datetime.date.fromisoformat(f"{start_str}-01")
            if start_str
            else start_boundary
        )
    except ValueError:
        start_date = start_boundary

    try:
        end_date = (
            datetime.date.fromisoformat(f"{end_str}-01") if end_str else end_boundary
        )
    except ValueError:
        end_date = end_boundary

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # 3. Liste des mois inclus
    selected_months = []
    curr = start_date
    while curr <= end_date:
        selected_months.append(curr)
        curr = advance_date(curr, 1)

    next_month_after_end = advance_date(end_date, 1)

    # 4. Requête globale filtrée
    transactions_qs = (
        Transaction.objects.filter(
            bank_account__owner__household=household,
            budget_month__gte=start_date,
            budget_month__lt=next_month_after_end,
        )
        .select_related(
            "bank_account", "bank_account__owner", "category", "recurring_expense"
        )
        .order_by("-transaction_date", "-created_at")
    )

    # 5. Groupement par mois
    history_by_month = []
    for m_date in reversed(selected_months):
        month_txs = [
            tx
            for tx in transactions_qs
            if tx.budget_month.year == m_date.year
            and tx.budget_month.month == m_date.month
        ]

        if month_txs:
            total_income = sum(
                (
                    tx.total_amount
                    for tx in month_txs
                    if tx.transaction_type == "INCOME"
                ),
                Decimal("0.00"),
            )
            total_expense = sum(
                (
                    tx.total_amount
                    for tx in month_txs
                    if tx.transaction_type == "EXPENSE"
                ),
                Decimal("0.00"),
            )
            net_balance = total_income - total_expense

            history_by_month.append(
                {
                    "date": m_date,
                    "transactions": month_txs,
                    "total_income": total_income,
                    "total_expense": total_expense,
                    "net_balance": net_balance,
                }
            )

    available_months = []
    curr = start_boundary
    while curr <= end_boundary:
        available_months.append(curr)
        curr = advance_date(curr, 1)

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "available_months": available_months,
        "history_by_month": history_by_month,
        "member": request.member,
        "breadcrumbs": ["Historique des transactions"],
    }

    return render(request, "budget/transactions/history_list.html", context)
