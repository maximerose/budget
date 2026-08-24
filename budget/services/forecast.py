import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from budget.models import (
    AccountType,
    BankAccount,
    HouseholdMember,
    Transaction,
    TransactionType,
)
from budget.models.category import CategoryType
from budget.models.forecast import MonthlyForecast
from budget.models.recurring import RecurringExpense, RecurringExpenseStatus
from budget.models.transaction import Transfer


def get_target_account_for_expense(
    expense: RecurringExpense, member: HouseholdMember
) -> BankAccount | None:
    """Détermine le compte bancaire cible selon les priorités."""
    if expense.default_bank_account:
        return expense.default_bank_account
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

    # 2.2 ÉTAPE 2 : Charges Variables (Prévisions liées à une catégorie)
    after_variables = after_recurring.copy()

    category_forecasts = MonthlyForecast.objects.filter(
        member=member,
        month__year=target_month.year,
        month__month=target_month.month,
        category__isnull=False,
        is_active=True,
    ).select_related("category")

    tr_accounts = [
        acc for acc in accounts if acc.account_type == AccountType.MEAL_VOUCHER
    ]
    default_account = next((acc for acc in accounts if acc.is_default), None)

    for forecast in category_forecasts:
        category = forecast.category

        if category.type in [CategoryType.INCOME, CategoryType.SAVING]:
            continue

        realized = Transaction.objects.filter(
            bank_account__owner=member,
            category_id=category.id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.EXPENSE,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        remaining = max(Decimal("0.00"), forecast.amount - realized)

        if remaining > Decimal("0.00"):
            if category.is_meal_voucher_eligible and tr_accounts:
                for tr_acc in tr_accounts:
                    if remaining <= Decimal("0.00"):
                        break
                    available_tr = max(
                        Decimal("0.00"), after_variables.get(tr_acc.id, Decimal("0.00"))
                    )

                    if available_tr > Decimal("0.00"):
                        tr_deduction = min(remaining, available_tr)
                        after_variables[tr_acc.id] -= tr_deduction
                        remaining -= tr_deduction

                if remaining > Decimal("0.00") and default_account:
                    after_variables[default_account.id] -= remaining
            else:
                if default_account:
                    after_variables[default_account.id] -= remaining

    # 2.3 ÉTAPE 3 : Épargne
    after_savings = after_variables.copy()

    saving_forecasts = MonthlyForecast.objects.filter(
        member=member,
        month__year=target_month.year,
        month__month=target_month.month,
        bank_account__isnull=False,
        bank_account__account_type=AccountType.SAVINGS,
        is_active=True,
    ).select_related("bank_account")

    for forecast in saving_forecasts:
        target_account = forecast.bank_account

        realized_transfers = Transfer.objects.filter(
            destination_account=target_account,
            source_account__owner=member,
            date__year=target_month.year,
            date__month=target_month.month,
        ).aggregate(Sum("amount"))["amount__sum"] or Decimal("0.00")

        realized_transactions = Transaction.objects.filter(
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            bank_account=target_account,
            transaction_type=TransactionType.INCOME,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        remaining = max(
            Decimal("0.00"),
            forecast.amount - realized_transfers - realized_transactions,
        )

        if remaining > Decimal("0.00"):
            if default_account:
                after_savings[default_account.id] -= remaining
            if target_account.id in after_savings:
                after_savings[target_account.id] += remaining

    # 2.4 ÉTAPE 4 : Revenus
    after_incomes = after_savings.copy()

    income_forecasts = [
        f for f in category_forecasts if f.category.type == CategoryType.INCOME
    ]

    for forecast in income_forecasts:
        realized = Transaction.objects.filter(
            bank_account__owner=member,
            category_id=forecast.category_id,
            budget_month__year=target_month.year,
            budget_month__month=target_month.month,
            transaction_type=TransactionType.INCOME,
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        remaining_to_receive = max(Decimal("0.00"), forecast.amount - realized)

        if remaining_to_receive > Decimal("0.00") and default_account:
            after_incomes[default_account.id] += remaining_to_receive

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