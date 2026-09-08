from decimal import Decimal

from django import template

register = template.Library()


@register.simple_tag
def build_progress_data(spent, allocated):
    try:
        spent_dec = Decimal(str(spent or 0))
        alloc_dec = Decimal(str(allocated or 0))
    except (ValueError, TypeError):
        spent_dec = Decimal("0.00")
        alloc_dec = Decimal("0.00")

    if alloc_dec <= 0:
        ratio = 100 if spent_dec > 0 else 0
    else:
        ratio = float((spent_dec / alloc_dec) * 100)

    percentage = min(100.0, max(0.0, ratio))

    # Couleur dynamique : Vert < 80%, Orange 80-100%, Rouge > 100%
    if ratio < 80:
        bg_color = "bg-action-primary"
        text_color = "text-action-primary"
    elif ratio <= 100:
        bg_color = "bg-action-warning"
        text_color = "text-action-warning"
    else:
        bg_color = "bg-action-danger"
        text_color = "text-action-danger"

    return {
        "percentage": round(percentage, 1),
        "ratio_raw": round(ratio, 1),
        "bg_color": bg_color,
        "text_color": text_color,
    }
