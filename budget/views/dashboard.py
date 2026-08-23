from django.shortcuts import render

from budget.models import BankAccount, HouseholdMember


def dashboard_view(request):
    member = HouseholdMember.objects.filter(is_active=True).first()
    accounts = []

    if member:
        accounts = BankAccount.objects.filter(owner=member, is_active=True)

    return render(
        request,
        "budget/dashboard.html",
        {
            "member": member,
            "accounts": accounts,
        },
    )
