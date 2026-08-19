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
