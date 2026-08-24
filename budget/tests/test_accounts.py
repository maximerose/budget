from decimal import Decimal

from django.test import TestCase

from budget.models import AccountType, BankAccount, HouseholdMember
from budget.models.account import Household, Visibility


class AccountModelsTestCase(TestCase):
    def setUp(self) -> None:
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime",
            household=self.household,
        )
        self.partner = HouseholdMember.objects.create(
            name="Laurie",
            household=self.household,
        )

        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_household_and_members_relationship(self) -> None:
        """Vérifie la relation One-to-Many entre un foyer et ses membres."""
        self.assertEqual(str(self.household), "Foyer Test")
        self.assertEqual(self.member.household, self.household)
        self.assertEqual(self.partner.household, self.household)

        # Vérifie qu'on peut récpérer tous les membres depuis le foyer
        self.assertEqual(self.household.members.count(), 2)

    def test_bank_account_str(self) -> None:
        self.assertEqual(
            str(self.bank_account), "Compte courant (Compte courant) Maxime"
        )

    def test_bank_account_visibility_default(self) -> None:
        """Vérifie que la visibilité par défaut d'un compte est partagée (SHARED)."""
        self.assertEqual(self.bank_account.visibility, Visibility.SHARED)

    def test_bank_account_visibility_private(self) -> None:
        """Vérifie qu'un compte privé conserve bien son statut."""
        private_account = BankAccount.objects.create(
            name="Compte Secret",
            account_type=AccountType.CHECKING,
            owner=self.member,
            visibility=Visibility.PRIVATE,
        )
        self.assertEqual(private_account.visibility, Visibility.PRIVATE)

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
