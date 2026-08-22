import datetime
from decimal import Decimal

from budget.models import (
    AccountType,
    BankAccount,
    HouseholdMember,
    MonthlyForecastShare,
    RecurringExpenseShare,
)


def calculate_monthly_projected_balances(
    member: HouseholdMember, month: datetime.date
) -> dict[str, dict[str, Decimal]]:
    """
    Calcule la cascade complète des soldes projetés par étape :
    - 'initial' : Solde actuel réel.
    - 'after_fixed' : Solde après déduction des charges fixes.
    - 'after_variables' : Solde après déduction des charges variables (avec déduction TR).
    - 'after_savings' : Solde après transfert vers les comptes d'épargne.
    - 'after_incomes' : Solde final après encaissement des revenus de fin de mois.
    """
    accounts = BankAccount.objects.filter(owner=member, is_active=True)

    # 1. Solde Initial
    initial = {acc.id: acc.current_balance for acc in accounts}

    # 2. ÉTAPE 1 : Après Charges Fixes
    after_fixed = initial.copy()
    recurring_shares = RecurringExpenseShare.objects.filter(
        bank_account__in=accounts,
        recurring_expense__is_active=True,
        recurring_expense__is_variable=False,
        is_active=True,
    )
    for share in recurring_shares:
        after_fixed[share.bank_account_id] -= share.amount

    # 3. ÉTAPE 2 : Après Charges Variables (Exclut revenus et épargne)
    after_variables = after_fixed.copy()
    forecast_shares = MonthlyForecastShare.objects.filter(
        forecast__member=member,
        forecast__month=month,
        forecast__is_active=True,
        is_active=True,
    ).select_related("forecast__category", "bank_account")

    tr_accounts = [
        acc for acc in accounts if acc.account_type == AccountType.MEAL_VOUCHER
    ]

    for share in forecast_shares:
        category = share.forecast.category
        amount = share.amount
        target_account = share.bank_account

        # Ne traite que les dépenses variables classiques (ni revenus, ni comptes épargne)
        if category.is_income or target_account.account_type == AccountType.SAVINGS:
            continue

        if category.is_meal_voucher_eligible and tr_accounts:
            for tr_acc in tr_accounts:
                available_tr = after_variables.get(tr_acc.id, Decimal("0.00"))
                if available_tr > Decimal("0.00"):
                    tr_deduction = min(amount, available_tr)
                    after_variables[tr_acc.id] -= tr_deduction
                    amount -= tr_deduction
                    if amount == Decimal("0.00"):
                        break

        if amount > Decimal("0.00"):
            after_variables[target_account.id] -= amount

    # 4. ÉTAPE 3 : Après Épargne (Prélèvements sur compte courant vers comptes épargne)
    after_savings = after_variables.copy()
    savings_shares = forecast_shares.filter(
        bank_account__account_type=AccountType.SAVINGS
    )

    for share in savings_shares:
        # Débite le compte courant par défaut (ou fallback) et crédite le compte d'épargne
        source_account_id = (
            share.bank_account.fallback_account_id
            or share.forecast.category.default_bank_account_id
        )
        if source_account_id and source_account_id in after_savings:
            after_savings[source_account_id] -= share.amount
        after_savings[share.bank_account_id] += share.amount

    # 5. ÉTAPE 4 : Après Revenus (Crédit des catégories de type revenu)
    after_incomes = after_savings.copy()
    income_shares = forecast_shares.filter(forecast__category__is_income=True)

    for share in income_shares:
        after_incomes[share.bank_account_id] += share.amount

    return {
        "initial": initial,
        "after_fixed": after_fixed,
        "after_variables": after_variables,
        "after_savings": after_savings,
        "after_incomes": after_incomes,
    }
