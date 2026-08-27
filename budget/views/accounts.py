from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from budget.forms import BankAccountForm
from budget.models import BankAccount, HouseholdMember
from budget.models.account import Visibility
from budget.utils import htmx_login_required


@login_required
def settings_accounts_list_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    accounts = BankAccount.objects.filter(
        Q(owner=member)
        | Q(owner__household=member.household, visibility=Visibility.SHARED),
        is_active=True,
    ).distinct()

    return render(
        request,
        "budget/settings/account_list.html",
        {
            "accounts": accounts,
            "member": member,
        },
    )


@htmx_login_required
def settings_account_form_view(
    request: Request, account_id: str | None = None
) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    account = None

    if account_id:
        account = get_object_or_404(
            BankAccount, id=account_id, owner=member, is_active=True
        )

    if request.method == "POST":
        form = BankAccountForm(
            request.POST, instance=account, household=member.household
        )

        if form.is_valid():
            new_account = form.save(commit=False)

            if not account_id:
                new_account.owner = member

            new_account.save()

            response = HttpResponse("")
            response["HX-Refresh"] = "true"

            return response
    else:
        form = BankAccountForm(instance=account, household=member.household)

    return render(
        request,
        "budget/components/modal.html",
        {
            "modal_title": "Modifier le compte" if account else "Nouveau compte",
            "modal_icon": "🏦",
            "has_cancel": True,
            "has_save": True,
            "form_id": "account-form",
            "modal_content_template": "budget/partials/settings/_modal_account_form.html",
            "form": form,
            "account": account,
        },
    )


@htmx_login_required
def settings_account_delete_view(request: Request, account_id: str) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    account = get_object_or_404(
        BankAccount,
        id=account_id,
        owner=member,
        is_active=True,
    )

    if request.method == "POST":
        account.is_active = False
        account.save(update_fields=["is_active"])

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)
