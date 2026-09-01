from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from budget.models import HouseholdMember
from budget.models.account import HouseholdInvitation
from budget.utils import htmx_login_required


@login_required
def settings_profile_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    household = member.household

    # Récupération de la dernière invitation valide
    invitations = HouseholdInvitation.objects.filter(
        household=household,
        accepted_by__isnull=True,
    ).order_by("-created_at")

    valid_invitation = next((inv for inv in invitations if inv.is_valid), None)

    invite_url = None

    if valid_invitation:
        invite_url = request.build_absolute_uri(
            reverse("join_household", args=[valid_invitation.token])
        )

    return render(
        request,
        "budget/settings/profile_list.html",
        {
            "member": member,
            "household": household,
            "invite_url": invite_url,
        },
    )


@htmx_login_required
def settings_profile_update(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")

        with transaction.atomic():
            if name:
                member.name = name
                member.save(update_fields=["name"])
            if email:
                request.user.email = email
                request.user.save(update_fields=["email"])

        response = HttpResponse("")
        response["HX-Refresh"] = "true"

        return response

    return HttpResponse("Méthode non autorisée", status=405)


@htmx_login_required
def settings_household_update(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            member.household.name = name
            member.household.save(update_fields=["name"])

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)


@htmx_login_required
def settings_generate_invite(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()

    if request.method == "POST":
        HouseholdInvitation.objects.create(
            household=member.household,
            created_by=request.user,
        )

        response = HttpResponse("")
        response["HX-Refresh"] = "true"

        return response

    return HttpResponse("Méthode non autorisée", status=405)
