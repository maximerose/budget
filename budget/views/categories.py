from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from budget.forms.category import CategoryForm
from budget.models import Category, HouseholdMember
from budget.utils import htmx_login_required


@login_required
def settings_categories_list_view(request: Request) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    categories = Category.objects.filter(household=member.household, is_active=True)

    return render(
        request,
        "budget/settings/category_list.html",
        {"categories": categories, "member": member},
    )


@htmx_login_required
def settings_category_form_view(
    request: Request, category_id: str | None = None
) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    category = None

    if category_id:
        category = get_object_or_404(
            Category, id=category_id, household=member.household, is_active=True
        )

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, household=member.household)
        if form.is_valid():
            new_category = form.save(commit=False)
            if not category_id:
                new_category.household = member.household
            new_category.save()

            response = HttpResponse("")
            response["HX-Refresh"] = "true"
            return response
    else:
        form = CategoryForm(instance=category, household=member.household)

    return render(
        request,
        "budget/components/modal.html",
        {
            "modal_title": "Modifier la catégorie"
            if category
            else "Nouvelle catégorie",
            "modal_icon": "🏷️",
            "has_cancel": True,
            "has_save": True,
            "form_id": "category-form",
            "modal_content_template": "budget/partials/settings/_modal_category_form.html",
            "form": form,
            "category": category,
        },
    )


@htmx_login_required
def settings_category_delete_view(request: Request, category_id: str) -> HttpResponse:
    member = HouseholdMember.objects.filter(user=request.user, is_active=True).first()
    category = get_object_or_404(
        Category, id=category_id, household=member.household, is_active=True
    )

    if request.method == "POST":
        category.is_active = False
        category.save(update_fields=["is_active"])

        response = HttpResponse("")
        response["HX-Refresh"] = "true"
        return response

    return HttpResponse("Méthode non autorisée", status=405)
