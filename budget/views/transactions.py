from decimal import Decimal
from urllib.request import Request

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from budget.models import (
    BankAccount,
    Category,
    HouseholdMember,
    Transaction,
    TransactionType,
)
from budget.models.account import Visibility
from budget.models.category import CategoryType
from budget.utils import htmx_login_required


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
def quick_expense_form_view(request: Request) -> HttpResponse:
    # Pour l'instant, on récupère le premier membre actif (ou celui de la session)
    current_member = HouseholdMember.objects.filter(
        user=request.user, is_active=True
    ).first()

    if request.method == "POST":
        total_amount = Decimal(request.POST.get("total_amount", "0.00"))
        label = request.POST.get("label", "")
        category_id = request.POST.get("category")
        bank_account_id = request.POST.get("bank_account")
        transaction_date = request.POST.get("transaction_date") or timezone.localdate()

        Transaction.objects.create(
            total_amount=total_amount,
            label=label,
            category_id=category_id,
            bank_account_id=bank_account_id,
            transaction_date=transaction_date,
            budget_month=transaction_date,
            transaction_type=TransactionType.EXPENSE,
        )

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    # On filtre les catégories et les comptes liés au FOYER (exclusion des revenus/épargne)
    categories = Category.objects.filter(
        is_active=True, household=current_member.household
    ).exclude(type__in=[CategoryType.INCOME, CategoryType.SAVING])

    accounts = BankAccount.objects.filter(
        Q(owner=current_member)
        | Q(owner__household=current_member.household, visibility=Visibility.SHARED),
        is_active=True,
    ).distinct()

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

    return render(
        request,
        "budget/partials/transactions/_modal_quick_expense.html",
        {
            "categories": categories,
            "accounts": account_options,
            "today": today,
        },
    )
