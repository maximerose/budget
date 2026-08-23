from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from budget.models import (
    BankAccount,
    Category,
    HouseholdMember,
    Transaction,
    TransactionType,
)


def quick_expense_form_view(request):
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
