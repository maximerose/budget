import datetime
import json
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

    min_tx_date = Transaction.objects.filter(
        bank_account__owner__household=household
    ).aggregate(m=Min("budget_month"))["m"]

    start_boundary = min_tx_date.replace(day=1) if min_tx_date else today
    end_boundary = today

    start_str = request.GET.get("start_month")
    end_str = request.GET.get("end_month")

    try:
        start_date = (
            datetime.date.fromisoformat(f"{start_str}-01")
            if start_str
            else start_boundary
        )
    except ValueError:
        start_date = start_boundary

    try:
        end_date = (
            datetime.date.fromisoformat(f"{end_str}-01") if end_str else end_boundary
        )
    except ValueError:
        end_date = end_boundary

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    selected_months = []
    curr = start_date
    while curr <= end_date:
        selected_months.append(curr)
        curr = advance_date(curr, 1)

    nb_period_months = len(selected_months) or 1
    next_month_after_end = advance_date(end_date, 1)

    range_txs = Transaction.objects.filter(
        bank_account__owner__household=household,
        budget_month__gte=start_date,
        budget_month__lt=next_month_after_end,
    )

    category_types = [
        (CategoryType.INCOME, "Revenus", "#10b981", "rgba(16, 185, 129, 0.1)"),
        (CategoryType.RECURRING, "Charges fixes", "#f43f5e", "rgba(244, 63, 94, 0.1)"),
        (
            CategoryType.VARIABLE,
            "Charges variables",
            "#f59e0b",
            "rgba(245, 158, 11, 0.1)",
        ),
        (CategoryType.SAVINGS, "Épargne", "#8b5cf6", "rgba(139, 92, 246, 0.1)"),
    ]

    FRENCH_MONTHS = [
        "Janv.",
        "Fév.",
        "Mars",
        "Avr.",
        "Mai",
        "Juin",
        "Juil.",
        "Août",
        "Sept.",
        "Oct.",
        "Nov.",
        "Déc.",
    ]
    chart_labels = [f"{FRENCH_MONTHS[m.month - 1]} {m.year}" for m in selected_months]

    chart_data_combined = {"labels": chart_labels, "datasets": []}
    individual_charts = {}
    period_summary = []

    colors_palette = [
        "#3b82f6",
        "#f43f5e",
        "#f59e0b",
        "#10b981",
        "#8b5cf6",
        "#14b8a6",
        "#ec4899",
        "#06b6d4",
    ]

    def get_net_amount(qs, expected_type):
        inc = qs.filter(transaction_type="INCOME").aggregate(s=Sum("total_amount"))[
            "s"
        ] or Decimal("0.00")
        exp = qs.filter(transaction_type="EXPENSE").aggregate(s=Sum("total_amount"))[
            "s"
        ] or Decimal("0.00")
        return (inc - exp) if expected_type == "INCOME" else (exp - inc)

    TOP_LIMIT = 5

    for cat_type_key, cat_type_label, border_color, bg_color in category_types:
        categories_data = []
        type_txs = range_txs.filter(category__type=cat_type_key)
        cats = (
            type_txs.values("category__id", "category__name")
            .distinct()
            .order_by("category__name")
        )

        type_total_period = Decimal("0.00")
        expected_type = "INCOME" if cat_type_key == CategoryType.INCOME else "EXPENSE"

        type_monthly_totals = [0.0] * len(selected_months)

        for c in cats:
            c_id = c["category__id"]
            c_name = c["category__name"]
            cat_txs = type_txs.filter(category_id=c_id)
            total_period = get_net_amount(cat_txs, expected_type)

            monthly_breakdown = []
            active_months_count = 0

            prev_month_date = start_date.replace(day=1) - datetime.timedelta(days=1)
            prev_qs = cat_txs.filter(
                budget_month__year=prev_month_date.year,
                budget_month__month=prev_month_date.month,
            )
            prev_amount = get_net_amount(prev_qs, expected_type)

            for m_idx, m_date in enumerate(selected_months):
                curr_qs = cat_txs.filter(
                    budget_month__year=m_date.year, budget_month__month=m_date.month
                )
                m_amount = get_net_amount(curr_qs, expected_type)

                if m_amount != 0:
                    active_months_count += 1

                if m_amount > prev_amount:
                    evo = "up"
                elif m_amount < prev_amount:
                    evo = "down"
                else:
                    evo = "same"

                monthly_breakdown.append(
                    {"date": m_date, "amount": m_amount, "evolution": evo}
                )
                type_monthly_totals[m_idx] += float(m_amount)
                prev_amount = m_amount

            divisor = Decimal(active_months_count or 1)
            type_total_period += total_period

            categories_data.append(
                {
                    "id": c_id,
                    "name": c_name,
                    "total_period": total_period,
                    "monthly_avg": total_period / divisor,
                    "active_months": active_months_count,
                    "months": monthly_breakdown,
                }
            )

        # Tri des catégories pour alimenter le graphique individuel
        sorted_cats_for_chart = sorted(
            categories_data, key=lambda item: item["total_period"], reverse=True
        )

        cat_datasets = []
        for i, c in enumerate(sorted_cats_for_chart):
            cat_monthly_values = [float(m["amount"]) for m in c["months"]]
            is_hidden_by_default = i >= TOP_LIMIT

            cat_datasets.append(
                {
                    "label": f" {c['name']}",
                    "data": cat_monthly_values,
                    "borderColor": colors_palette[i % len(colors_palette)],
                    "backgroundColor": "transparent",
                    "pointBackgroundColor": colors_palette[i % len(colors_palette)],
                    "tension": 0.4,
                    "borderWidth": 2,
                    "pointRadius": 3,
                    "pointHitRadius": 10,
                    "hidden": is_hidden_by_default,
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

        # Courbe du graphique global
        chart_data_combined["datasets"].append(
            {
                "label": f" {cat_type_label}",
                "data": type_monthly_totals,
                "borderColor": border_color,
                "backgroundColor": bg_color,
                "pointBackgroundColor": border_color,
                "fill": True,
                "tension": 0.4,
                "pointRadius": 3,
                "pointHitRadius": 10,
            }
        )

        individual_charts[cat_type_key] = {
            "labels": chart_labels,
            "datasets": cat_datasets,
        }

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
        "chart_data_combined_json": json.dumps(chart_data_combined),
        "individual_charts_json": json.dumps(individual_charts),
        "breadcrumbs": ["Statistiques"],
    }

    return render(request, "budget/statistics/statistics_list.html", context)