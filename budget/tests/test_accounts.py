from decimal import Decimal

from django.test import TestCase

from budget.models import AccountType, BankAccount, HouseholdMember


class AccountModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_bank_account_str(self) -> None:
        self.assertEqual(str(self.bank_account), "Compte courant (Compte courant)")

    def test_meal_voucher_account_default_limit(self) -> None:
        # Un compte TR sans limite spécifiée doit recevoir 25.00 par défaut via clean()
        tr_account = BankAccount.objects.create(
            name="Swile",
            account_type=AccountType.MEAL_VOUCHER,
            owner=self.member,
        )
        self.assertEqual(tr_account.daily_meal_voucher_limit, Decimal("25.00"))

    def test_checking_account_forces_null_limit(self) -> None:
        # Un compte courant ne doit jamais avoir de limite TR, même si on tente de lui en assigner une
        checking_account = BankAccount.objects.create(
            name="Compte sans TR",
            account_type=AccountType.CHECKING,
            owner=self.member,
            daily_meal_voucher_limit=Decimal("50.00"),
        )
        self.assertIsNone(checking_account.daily_meal_voucher_limit)
