import calendar
import datetime
from decimal import Decimal

from django.db.models.aggregates import Sum

from budget.models.account import AccountType
from budget.models.transaction import Transaction


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
