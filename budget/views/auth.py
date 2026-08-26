from urllib.request import Request

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from budget.forms import RegisterForm
from budget.models.account import Household, HouseholdMember


def register_view(request: Request) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Création automatique du foyer et du profil
                household = Household.objects.create(name=f"Foyer de {user.username}")
                HouseholdMember.objects.create(
                    name=user.username,
                    user=user,
                    household=household,
                )
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})
