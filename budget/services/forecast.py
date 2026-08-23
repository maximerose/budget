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
from budget.models.recurring import RecurringExpense, RecurringExpenseStatus


def get_target_account_for_expense(
    expense: RecurringExpense, member: HouseholdMember
) -> BankAccount | None:
    """Détermine le compte bancaire cible selon les priorités."""
    if expense.default_bank_account:
        return expense.default_bank_account
    if expense.category and expense.category.default_bank_account:
        return expense.category.default_bank_account
    return BankAccount.objects.filter(
        owner=member, is_default=True, is_active=True
    ).first()


def calculate_monthly_projected_balances(
    member: HouseholdMember, month: datetime.date
) -> dict[str, dict[str, Decimal]]:
    accounts = BankAccount.objects.filter(owner=member, is_active=True)
    today = timezone.localdate().replace(day=1)
    target_month = month.replace(day=1)

    initial = {acc.id: acc.current_balance for acc in accounts}

    if target_month < today:
        return {
            "initial": initial,
            "after_recurring": initial.copy(),
            "after_variables": initial.copy(),
            "after_savings": initial.copy(),
            "after_incomes": initial.copy(),
        }

    # 2.1 ÉTAPE 1 : Charges Fixes (Gestion hybride : Shares ou Expense direct)
    after_recurring = initial.copy()
    recurring_expenses = RecurringExpense.objects.filter(
        is_active=True,
        is_variable=False,
    ).select_related("category", "default_bank_account")

    for expense in recurring_expenses:
        shares = expense.shares.filter(is_active=True)

        if shares.exists():
            # Cas 1 : Répartition explicite via des Shares
            for share in shares:
                if share.bank_account_id not in after_recurring:
                    continue
                real_transactions = Transaction.objects.filter(
                    bank_account_id=share.bank_account_id,
                    recurring_expense=expense,
                    budget_month__year=target_month.year,
                    budget_month__month=target_month.month,
                    transaction_type=TransactionType.EXPENSE,
                )
                if not real_transactions.exists():
                    after_recurring[share.bank_account_id] -= share.amount
        else:
            # Cas 2 : Pas de Share -> Compte cible déterminé automatiquement
            target_account = get_target_account_for_expense(expense, member)
            if target_account and target_account.id in after_recurring:
                real_transactions = Transaction.objects.filter(
                    bank_account_id=target_account.id,
                    recurring_expense=expense,
                    budget_month__year=target_month.year,
                    budget_month__month=target_month.month,
                    transaction_type=TransactionType.EXPENSE,
                )
                if not real_transactions.exists():
                    after_recurring[target_account.id] -= expense.total_amount

    # 2.2 ÉTAPE 2 : Charges Variables
    after_variables = after_recurring.copy()
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
        "after_recurring": after_recurring,
        "after_variables": after_variables,
        "after_savings": after_savings,
        "after_incomes": after_incomes,
    }


def get_recurring_expenses_with_status(
    member: HouseholdMember, month: datetime.date
) -> list[dict]:
    target_month = month.replace(day=1)
    expenses = RecurringExpense.objects.filter(
        is_active=True,
        is_variable=False,
    ).select_related("category", "default_bank_account")

    results = []
    for expense in expenses:
        shares = expense.shares.filter(is_active=True)

        if shares.exists():
            for share in shares:
                if share.bank_account.owner != member:
                    continue
                realized = Transaction.objects.filter(
                    bank_account_id=share.bank_account_id,
                    recurring_expense=expense,
                    budget_month__year=target_month.year,
                    budget_month__month=target_month.month,
                    transaction_type=TransactionType.EXPENSE,
                ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

                status = (
                    RecurringExpenseStatus.WAITING
                    if realized == Decimal("0.00")
                    else (
                        RecurringExpenseStatus.PARTIAL
                        if realized < share.amount
                        else RecurringExpenseStatus.COMPLETED
                    )
                )

                results.append(
                    {
                        "expense": expense,
                        "bank_account": share.bank_account,
                        "expected_amount": share.amount,
                        "realized_amount": realized,
                        "status": status,
                    }
                )
        else:
            target_account = get_target_account_for_expense(expense, member)
            if target_account and target_account.owner == member:
                realized = Transaction.objects.filter(
                    bank_account_id=target_account.id,
                    recurring_expense=expense,
                    budget_month__year=target_month.year,
                    budget_month__month=target_month.month,
                    transaction_type=TransactionType.EXPENSE,
                ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

                status = (
                    RecurringExpenseStatus.WAITING
                    if realized == Decimal("0.00")
                    else (
                        RecurringExpenseStatus.PARTIAL
                        if realized < expense.total_amount
                        else RecurringExpenseStatus.COMPLETED
                    )
                )

                results.append(
                    {
                        "expense": expense,
                        "bank_account": target_account,
                        "expected_amount": expense.total_amount,
                        "realized_amount": realized,
                        "status": status,
                    }
                )

    return results


def create_transaction_from_recurring_expense(
    expense: RecurringExpense,
    bank_account: BankAccount,
    amount: Decimal | None = None,
    budget_month: datetime.date | None = None,
    label: str | None = None,
) -> Transaction:
    today = timezone.localdate()
    month = budget_month.replace(day=1) if budget_month else today.replace(day=1)

    transaction_amount = amount if amount is not None else expense.total_amount
    transaction_label = label or expense.label

    return Transaction.objects.create(
        bank_account=bank_account,
        category=expense.category,
        recurring_expense=expense,
        total_amount=transaction_amount,
        label=transaction_label,
        transaction_date=today,
        budget_month=month,
        transaction_type=TransactionType.EXPENSE,
    )
