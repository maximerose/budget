import datetime
from decimal import Decimal
from urllib.request import Request

from django.contrib.auth.decorators import login_required
from django.db.models import Min, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from budget.models import Transaction
from budget.models.category import CategoryType
from budget.utils import advance_date


@login_required
def statistics_view(request: Request) -> HttpResponse:
    household = request.household
    today = timezone.localdate().replace(day=1)

    # 1. Première transaction historique du foyer
    min_tx_date = Transaction.objects.filter(
        bank_account__owner__household=household
    ).aggregate(m=Min("budget_month"))["m"]

    # Borne minimale par défaut : le mois le plus ancien trouvé, sinon le mois courant
    start_boundary = min_tx_date.replace(day=1) if min_tx_date else today
    end_boundary = today

    # 2. Bornes sélectionnées dans le formulaire
    start_str = request.GET.get("start_month")
    end_str = request.GET.get("end_month")

    try:
        start_date = (
            datetime.date.fromisoformat(f"{start_str}-01")
            if start_str
            else start_boundary  # <--- Correction : démarre au plus ancien par défaut !
        )
    except ValueError:
        start_date = start_boundary

    try:
        end_date = (
            datetime.date.fromisoformat(f"{end_str}-01") if end_str else end_boundary
        )
    except ValueError:
        end_date = end_boundary

    # Inversion de sécurité si start > end
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # 3. Liste des mois inclus dans la période filtrée
    selected_months = []
    curr = start_date
    while curr <= end_date:
        selected_months.append(curr)
        curr = advance_date(curr, 1)

    nb_period_months = len(selected_months) or 1
    next_month_after_end = advance_date(end_date, 1)

    # 4. Requête des transactions sur la plage sélectionnée
    range_txs = Transaction.objects.filter(
        bank_account__owner__household=household,
        budget_month__gte=start_date,
        budget_month__lt=next_month_after_end,
    )

    # 5. Ventilation par type de catégorie
    category_types = [
        (CategoryType.INCOME, "Revenus"),
        (CategoryType.RECURRING, "Charges fixes"),
        (CategoryType.VARIABLE, "Charges variables"),
        (CategoryType.SAVINGS, "Épargne"),
    ]

    period_summary = []

    for cat_type_key, cat_type_label in category_types:
        categories_data = []
        type_txs = range_txs.filter(category__type=cat_type_key)

        cats = (
            type_txs.values("category__id", "category__name")
            .distinct()
            .order_by("category__name")
        )

        type_total_period = Decimal("0.00")

        for c in cats:
            c_id = c["category__id"]
            cat_txs = type_txs.filter(category_id=c_id)

            total_period = cat_txs.aggregate(s=Sum("total_amount"))["s"] or Decimal(
                "0.00"
            )

            # Reconstitution mois par mois & comptage des mois actifs
            monthly_breakdown = []
            active_months_count = 0

            for m_date in selected_months:
                m_amount = cat_txs.filter(
                    budget_month__year=m_date.year,
                    budget_month__month=m_date.month,
                ).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")

                if m_amount > 0:
                    active_months_count += 1

                monthly_breakdown.append({"date": m_date, "amount": m_amount})

            # MOYENNE : On divise par les mois actifs (Option B).
            # Si tu préfères diviser par le nombre total de mois du filtre (Option A),
            # remplace `active_months_count or 1` par `nb_period_months`.
            divisor = Decimal(active_months_count or 1)
            monthly_avg = total_period / divisor

            type_total_period += total_period

            categories_data.append(
                {
                    "id": c_id,
                    "name": c["category__name"],
                    "total_period": total_period,
                    "monthly_avg": monthly_avg,
                    "active_months": active_months_count,
                    "months": monthly_breakdown,
                }
            )

        period_summary.append(
            {
                "type_key": cat_type_key,
                "label": cat_type_label,
                "categories": categories_data,
                "total_period": type_total_period,
                "monthly_avg": type_total_period / Decimal(nb_period_months),
            }
        )

    # 6. Options pour le <select> du filtre
    available_months = []
    curr = start_boundary
    while curr <= end_boundary:
        available_months.append(curr)
        curr = advance_date(curr, 1)

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "available_months": available_months,
        "selected_months": selected_months,
        "period_summary": period_summary,
        "breadcrumbs": ["Statistiques"],
    }

    return render(request, "budget/statistics/statistics_list.html", context)
