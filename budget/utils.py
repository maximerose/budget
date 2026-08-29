import calendar
import datetime
from decimal import Decimal
from functools import wraps

from django.db.models.aggregates import Sum
from django.http import HttpResponse

from budget.models.account import AccountType
from budget.models.transaction import Transaction


def htmx_login_required(view_func):
    """Décorateur pour bloquer l'accès aux vues HTMX si non connecté."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponse("Non autorisé", status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def calculate_budget_month(
    ref_date: datetime.date, target_year: int, target_month: int
) -> datetime:
    """Calcule le budget_month selon que le mois cible est antérieur, égal ou postérieur"""
    ref_key = (ref_date.year, ref_date.month)
    target_key = (target_year, target_month)

    if target_key < ref_key:
        # Antérieur -> dernier jour du mois cible
        last_day = calendar.monthrange(target_year, target_month)[1]
        return datetime.date(target_year, target_month, last_day)
    elif target_key > ref_key:
        # Postérieur -> Premier jour du mois cible
        return datetime.date(target_year, target_month, 1)
    else:
        # Même mois -> On conserve la date de référence (ou transaction_date)
        return ref_date


def get_remaining_meal_voucher_ceiling(
    transaction_date: datetime.date, bank_account, exclude_transaction_pk=None
) -> Decimal | None:
    """
    Calcule le plafond journalier des tickets resto restant pour un membre.
    Retourne None si le membre ne possède pas de compte de tickets resto.
    """
    # Si ce n'est pas un compte de type tickets resto, il n'y a pas de plafond TR
    if bank_account.account_type != AccountType.MEAL_VOUCHER:
        return None

    limit = bank_account.daily_meal_voucher_limit or Decimal("25.00")

    qs = Transaction.objects.filter(
        transaction_date=transaction_date,
        category__is_meal_voucher_eligible=True,
        bank_account=bank_account,
    )

    if exclude_transaction_pk:
        qs = qs.exclude(pk=exclude_transaction_pk)

    spent_today = qs.aggregate(Sum("meal_voucher_amount"))[
        "meal_voucher_amount__sum"
    ] or Decimal("0.00")

    return max(Decimal("0.00"), limit - spent_today)


def advance_date(start_date: datetime.date, months_to_add: int) -> datetime.date:
    """Fait avancer une date d'un certain nombre de mois en gérant les fins de mois."""
    month_zero_indexed = start_date.month - 1 + months_to_add
    new_year = start_date.year + month_zero_indexed // 12
    new_month = month_zero_indexed % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    return datetime.date(new_year, new_month, min(start_date.day, last_day))
