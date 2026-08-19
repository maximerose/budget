import calendar
import datetime


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
