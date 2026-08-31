from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models.account import (
    AccountType,
    BankAccount,
    Household,
    HouseholdMember,
)
from core.models import Visibility

User = get_user_model()


class SettingsAccountsTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="maxime", password="password123")
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime",
            household=self.household,
            user=self.user,
        )
        self.client.force_login(self.user)

        self.account = BankAccount.objects.create(
            name="Compte Courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
            is_default=True,
        )

    def test_account_list_view(self) -> None:
        """Vérifie l'affichage de la liste des comptes"""
        url = reverse("settings_accounts")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "budget/settings/account_list.html")
        self.assertIn("accounts", response.context)

    def test_account_create_get(self) -> None:
        """Vérifie l'affichage du formulaire de création de compte."""
        url = reverse("settings_account_create")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "budget/partials/settings/_modal_account_form.html"
        )

    def test_account_create_post(self) -> None:
        """Vérifie la création d'un nouveau compte via POST."""
        url = reverse("settings_account_create")
        data = {
            "name": "Livret A",
            "account_type": AccountType.SAVINGS,
            "current_balance": "5000.00",
            "visibility": Visibility.SHARED,
            "is_default": False,
            "owner": str(self.member.id),
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")
        self.assertEqual(BankAccount.objects.count(), 2)

    def test_account_update_post(self) -> None:
        """Vérifie la modification d'un compte existant."""
        url = reverse("settings_account_update", args=[self.account.id])
        data = {
            "name": "Compte Courant Modifié",
            "account_type": AccountType.CHECKING,
            "current_balance": "1500.00",
            "visibility": Visibility.PRIVATE,
            "is_default": True,
            "owner": str(self.member.id),
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")
        self.account.refresh_from_db()
        self.assertEqual(self.account.name, "Compte Courant Modifié")

    def test_account_update_get(self) -> None:
        """Vérifie l'affichage du formulaire de modification."""
        url = reverse("settings_account_update", args=[self.account.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "budget/partials/settings/_modal_account_form.html"
        )
        self.assertEqual(response.context["account"], self.account)

    def test_account_delete_post(self) -> None:
        """Vérifie le soft-delete d'un compte."""
        url = reverse("settings_account_delete", args=[self.account.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")

        self.account.refresh_from_db()
        self.assertFalse(self.account.is_active)
