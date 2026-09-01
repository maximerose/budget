from urllib.request import Request

from django.contrib.auth import login
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from budget.forms import RegisterForm
from budget.models.account import Household, HouseholdInvitation, HouseholdMember
from budget.models.category import Category
from budget.models.recurring import RecurringExpense
from budget.utils import merge_categories


def join_household_view(request: Request, token: str) -> HttpResponse:
    """Gère le clic sur un lien magique d'invitation."""
    invitation = get_object_or_404(HouseholdInvitation, token=token)

    if not invitation.is_valid:
        return render(request, "registration/invite_error.html", status=400)

    # Si l'utilisateur est connecté, on lui demande confirmation
    if request.user.is_authenticated:
        if request.method == "POST":
            member = HouseholdMember.objects.filter(
                user=request.user, is_active=True
            ).first()
            if member:
                with transaction.atomic():
                    old_household = member.household
                    new_household = invitation.household

                    if old_household and old_household != new_household:
                        # 1. Traitement des catégories (auto-merge)
                        old_categories = Category.objects.filter(
                            household=old_household, is_active=True
                        )

                        for old_cat in old_categories:
                            # Cheche une catégorie homonyme dans le nouveau foyer
                            new_cat = Category.objects.filter(
                                household=new_household,
                                name__iexact=old_cat.name,
                                is_active=True,
                            ).first()

                            if new_cat:
                                merge_categories(old_cat, new_cat)
                            else:
                                # B. Import direct (si la catégorie n'existe pas)
                                old_cat.household = new_household
                                old_cat.save(update_fields=["household"])

                        # 2. Transfert des charges fixes vers le nouveau foyer
                        RecurringExpense.objects.filter(household=old_household).update(
                            household=new_household
                        )

                        # 3. Désactivation de l'ancien foyer s'il se retrouve vide
                        if (
                            not old_household.members.exclude(id=member.id)
                            .filter(is_active=True)
                            .exists()
                        ):
                            old_household.is_active = False
                            old_household.save(update_fields=["is_active"])

                    # 4. Assigner le membre au nouveau foyer
                    member.household = new_household
                    member.save(update_fields=["household"])

                    invitation.accepted_by = request.user
                    invitation.save(update_fields=["accepted_by"])

                return redirect("dashboard")

        # Requête GET : On affiche la page de confirmation
        return render(
            request, "registration/invite_confirm.html", {"invitation": invitation}
        )

    # S'il n'est pas connecté, on sauvegarde le token et on l'envoie s'inscrire
    request.session["invite_token"] = str(invitation.token)
    return redirect("register")


def register_view(request: Request) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()

                # --- LOGIQUE D'INVITATION ---
                token = request.session.get("invite_token")
                invitation = None

                if token:
                    invitation = HouseholdInvitation.objects.filter(
                        token=token, accepted_by__isnull=True
                    ).first()

                if invitation and invitation.is_valid:
                    # L'utilisateur rejoint le foyer existant
                    household = invitation.household
                    invitation.accepted_by = user
                    invitation.save()
                    del request.session["invite_token"]
                else:
                    # Création automatique d'un nouveau foyer
                    household = Household.objects.create(
                        name=f"Foyer de {user.username}"
                    )

                HouseholdMember.objects.create(
                    name=user.username,
                    user=user,
                    household=household,
                )

            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})
