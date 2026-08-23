import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    HouseholdMember,
    MonthlyForecastShare,
    RecurringExpenseShare,
    Transaction,
    TransactionType,
)
from budget.models.recurring import RecurringExpenseStatus


def calculate_monthly_projected_balances(
    member: HouseholdMember, month: datetime.date
) -> dict[str, dict[str, Decimal]]:
    accounts = BankAccount.objects.filter(owner=member, is_active=True)
    today = timezone.localdate().replace(day=1)
    target_month = month.replace(day=1)

    initial = {acc.id: acc.current_balance for acc in accounts}

    # 1. MOIS PASSÉ (M < actuel) : Clôturé, le solde réel en BDD fait foi.
    if target_month < today:
        return {
            "initial": initial,
            "after_fixed": initial.copy(),
            "after_variables": initial.copy(),
            "after_savings": initial.copy(),
            "after_incomes": initial.copy(),
        }

    # 2. MOIS EN COURS OU FUTUR (M >= actuel)
    # 2.1 ÉTAPE 1 : Charges Fixes
    after_fixed = initial.copy()
    recurring_shares = RecurringExpenseShare.objects.filter(
        bank_account__in=accounts,
        recurring_expense__is_active=True,
        recurring_expense__is_variable=False,
        is_active=True,
    ).select_related("recurring_expense")

    for share in recurring_shares:
        # 1. Cherche si des transactions réelles existent pour cette catégorie sur ce mois
        real_transactions = Transaction.objects.filter(
            bank_account_id=share.bank_account_id,
            category_id=share.recurring_expense.category_id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.EXPENSE,
        )

        if real_transactions.exists():
            # Si déjà prélevé : la transaction a DÉJÀ été débitée de current_balance en BDD.
            # On ne déduit donc rien de plus du solde actuel !
            continue
        else:
            # Si pas encore prélevé : on déduit le montant prévisionnel théorique
            after_fixed[share.bank_account_id] -= share.amount

    # 2.2 ÉTAPE 2 : Charges Variables
    after_variables = after_fixed.copy()
    forecast_shares = MonthlyForecastShare.objects.filter(
        forecast__member=member,
        forecast__month__year=target_month.year,
        forecast__month__month=target_month.month,
        forecast__is_active=True,
        is_active=True,
    ).select_related("forecast__category", "bank_account")

    tr_accounts = [
        acc for acc in accounts if acc.account_type == AccountType.MEAL_VOUCHER
    ]

    for share in forecast_shares:
        category = share.forecast.category
        target_account = share.bank_account

        is_savings = (
            target_account.account_type == AccountType.SAVINGS
            or category.default_bank_account_id
            and BankAccount.objects.filter(
                id=category.default_bank_account_id,
                account_type=AccountType.SAVINGS,
            ).exists()
        )

        if category.is_income or is_savings:
            continue

        realized = Transaction.objects.filter(
            bank_account_id=share.bank_account_id,
            category_id=category.id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.EXPENSE,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        amount = max(Decimal("0.00"), share.amount - realized)

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

    # 2.3 ÉTAPE 3 : Épargne
    after_savings = after_variables.copy()
    for share in forecast_shares:
        category = share.forecast.category
        target_account = share.bank_account

        is_savings = (
            target_account.account_type == AccountType.SAVINGS
            or category.default_bank_account_id
            and BankAccount.objects.filter(
                id=category.default_bank_account_id,
                account_type=AccountType.SAVINGS,
            ).exists()
        )

        if is_savings and not category.is_income:
            after_savings[share.bank_account_id] -= share.amount
            if category.default_bank_account_id:
                after_savings[category.default_bank_account_id] += share.amount

    # 2.4 ÉTAPE 4 : Revenus
    after_incomes = after_savings.copy()
    income_shares = forecast_shares.filter(forecast__category__is_income=True)

    for share in income_shares:
        realized = Transaction.objects.filter(
            bank_account_id=share.bank_account_id,
            category_id=share.forecast.category_id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.INCOME,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")
        remaining_to_receive = max(Decimal("0.00"), share.amount - realized)
        after_incomes[share.bank_account_id] += remaining_to_receive

    return {
        "initial": initial,
        "after_fixed": after_fixed,
        "after_variables": after_variables,
        "after_savings": after_savings,
        "after_incomes": after_incomes,
    }


def get_recurring_expenses_with_status(
    member: HouseholdMember, month: datetime.date
) -> list[dict]:
    """
    Retourne la liste des charges fixes d'un membre avec leur montant réalisé
    et leur statut (WAITING, PARTIAL, COMPLETED) pour un mois donné.
    """
    target_month = month.replace(day=1)

    shares = RecurringExpenseShare.objects.filter(
        bank_account__owner=member,
        bank_account__is_active=True,
        recurring_expense__is_active=True,
        recurring_expense__is_variable=False,
        is_active=True,
    ).select_related("recurring_expense", "bank_account")

    results = []
    for share in shares:
        # 1. On somme les transactions du moi sur cette catégorie
        realized = Transaction.objects.filter(
            bank_account_id=share.bank_account_id,
            category_id=share.recurring_expense.category_id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.EXPENSE,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        # 2. On détermine le statut
        if realized == Decimal("0.00"):
            status = RecurringExpenseStatus.WAITING
        elif realized < share.amount:
            status = RecurringExpenseStatus.PARTIAL
        else:
            status = RecurringExpenseStatus.COMPLETED

        # 3. On ajoute le dictionnaire à la liste
        results.append(
            {
                "share": share,
                "recurring_expense": share.recurring_expense,
                "expected_amount": share.amount,
                "realized_amount": realized,
                "status": status,
            }
        )

    return results


def create_transaction_from_recurring_expense(
    share: RecurringExpenseShare,
    amount: Decimal | None = None,
    budget_month: datetime.date | None = None,
    label: str | None = None,
) -> Transaction:
    """
    Crée une Transaction réelle depuis une part de charge fixe.
    Renseigne automatiquement la relation recurring_expense.
    """
    expense = share.recurring_expense
    today = timezone.localdate()
    month = budget_month.replace(day=1) if budget_month else today.replace(day=1)

    transaction_amount = amount if amount is not None else share.amount
    transaction_label = label or expense.label

    return Transaction.objects.create(
        bank_account=share.bank_account,
        category=expense.category,
        recurring_expense=expense,
        total_amount=transaction_amount,
        label=transaction_label,
        transaction_date=today,
        budget_month=month,
        transaction_type=TransactionType.EXPENSE,
    )
