from decimal import Decimal
from urllib import response
from urllib.request import Request

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


def adjust_account_balance_view(
    request: Request, account_id: str
) -> HttpResponse | None:
    account = get_object_or_404(BankAccount, id=account_id)

    if request.method == "POST":
        new_balance = Decimal(request.POST.get("new_balance", "0.00"))

        # On met à jou le solde du compte et la date
        account.current_balance = new_balance
        account.save()

        # On ferme la modale et on rafraîchit la pagepour voir le nouveau solde
        response = HttpResponse("")
        response["HX-Refresh"] = "true"

        return response

    return render(
        request,
        "budget/partials/_modal_adjust_balance.html",
        {"account": account},
    )


def quick_expense_form_view(request: Request) -> HttpResponse:
    # Pour l'instant, on récupère le premier membre actif (ou celui de la session)
    current_member = HouseholdMember.objects.filter(is_active=True).first()

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

    # On filtre les catégories et les comptes du membre connecté uniquement
    categories = Category.objects.filter(
        is_active=True, is_income=False, owner=current_member
    )
    accounts = BankAccount.objects.filter(is_active=True, owner=current_member)
    today = timezone.localdate()

    return render(
        request,
        "budget/partials/_modal_quick_expense.html",
        {
            "categories": categories,
            "accounts": accounts,
            "today": today,
        },
    )
