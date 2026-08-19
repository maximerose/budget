from decimal import Decimal
from django.test import TestCase
from budget.models import AccountType, BankAccount, HouseholdMember


class SoftDeleteTestCase(TestCase):
    def setUp(self) -> None:
        self.member = HouseholdMember.objects.create(name="Maxime")
        self.bank_account = BankAccount.objects.create(
            name="Compte courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    def test_soft_delete_is_active_flag(self) -> None:
        """Vérifie que le modèle gère bien le flag is_active par défaut à True."""
        self.assertTrue(self.bank_account.is_active)

        # Simulation d'un soft delete (passage de is_active à False)
        self.bank_account.is_active = False
        self.bank_account.save(update_fields=["is_active"])

        self.bank_account.refresh_from_db()
        self.assertFalse(self.bank_account.is_active)
