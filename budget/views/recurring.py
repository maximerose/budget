from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from budget.forms.recurring import RecurringExpenseForm, RecurringExpenseShareForm
from budget.models import HouseholdMember, RecurringExpense
from budget.models.account import BankAccount
from budget.models.recurring import RecurringExpenseShare
from budget.services.forecast import get_recurring_expenses_with_status
from budget.utils import get_target_month_from_request, htmx_login_required


@login_required
@require_GET
def settings_recurring_list_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    today = get_target_month_from_request(request)

    recurring_expenses = get_recurring_expenses_with_status(member, today)

    return render(
        request,
        "budget/settings/recurring_list.html",
        {"recurring_expenses": recurring_expenses, "member": member},
    )


@htmx_login_required
@require_http_methods(["GET", "POST"])
def settings_recurring_form_view(
    request: Request, expense_id: str | None = None
) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    expense = None

    if expense_id:
        expense = get_object_or_404(
            RecurringExpense, id=expense_id, household=member.household, is_active=True
        )

    if request.method == "POST":
        form = RecurringExpenseForm(
            request.POST, instance=expense, household=member.household
        )
        if form.is_valid():
            new_expense = form.save(commit=False)
            if not expense_id:
                new_expense.household = member.household
                # Par défaut, le créateur devient le propriétaire de la charge (même si elle est partagée)
                new_expense.owner = member
            new_expense.save()

            response = HttpResponse("")
            response["HX-Refresh"] = "true"
            return response
    else:
        form = RecurringExpenseForm(instance=expense, household=member.household)

    return render(
        request,
        "budget/components/modal.html",
        {
            "modal_title": "Modifier la charge" if expense else "Nouvelle charge fixe",
            "modal_icon": "📅",
            "has_cancel": True,
            "has_save": True,
            "form_id": "recurring-form",
            "modal_content_template": "budget/partials/settings/_modal_recurring_form.html",
            "form": form,
            "expense": expense,
        },
    )


@htmx_login_required
def settings_recurring_delete_view(request: Request, expense_id: str) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    expense = get_object_or_404(
        RecurringExpense, id=expense_id, household=member.household, is_active=True
    )

    if request.method == "POST":
        expense.is_active = False
        expense.save(update_fields=["is_active"])

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)


@htmx_login_required
def settings_recurring_shares_view(request: Request, expense_id: str) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    expense = get_object_or_404(
        RecurringExpense,
        id=expense_id,
        household=member.household,
        is_active=True,
    )
    shares = expense.shares.filter(is_active=True)
    remaining = expense.get_remaining_amount_to_split()

    accounts = BankAccount.objects.filter(
        owner__household=member.household, is_active=True
    )
    account_options = [
        {
            "id": acc.id,
            "name": f"{acc.name} ({acc.owner.name})"
            if acc.owner_id != member.id
            else acc.name,
        }
        for acc in accounts
    ]

    if request.method == "POST":
        form = RecurringExpenseShareForm(request.POST, household=member.household)

        if form.is_valid():
            share = form.save(commit=False)
            share.recurring_expense = expense

            try:
                share.full_clean()
                share.save()

                response = HttpResponse("")
                response["HX-Refresh"] = "true"

                return response
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = RecurringExpenseShareForm(household=member.household)

    return render(
        request,
        "budget/components/modal.html",
        {
            "modal_title": f"Répartition : {expense.label}",
            "modal_icon": "🔀",
            "has_cancel": True,
            "has_save": False,
            "modal_content_template": "budget/partials/settings/_modal_recurring_shares.html",
            "form": form,
            "expense": expense,
            "shares": shares,
            "remaining": remaining,
            "member": member,
            "account_options": account_options,
        },
    )


@htmx_login_required
def settings_recurring_share_delete_view(
    request: Request, expense_id: str, share_id: str
) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    expense = get_object_or_404(
        RecurringExpense, id=expense_id, household=member.household, is_active=True
    )
    share = get_object_or_404(
        RecurringExpenseShare, id=share_id, recurring_expense=expense, is_active=True
    )

    if request.method == "POST":
        share.is_active = False
        share.save(update_fields=["is_active"])
        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)
