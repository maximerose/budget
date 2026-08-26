from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models.account import AccountType, BankAccount, HouseholdMember

User = get_user_model()


class DashboardViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="maxime", password="password123")
        self.member = HouseholdMember.objects.create(name="Maxime", user=self.user)
        self.client.force_login(self.user)

        self.account = BankAccount.objects.create(
            name="Compte Courant",
            account_type=AccountType.CHECKING,
            owner=self.member,
            current_balance=Decimal("1000.00"),
        )

    # --- TESTS DU DASHBOARD PRINCIPAL ---

    def test_dashboard_view_with_active_member(self) -> None:
        """Vérifie que le dashboard charge correctement avec un membre actif."""
        url = reverse("dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "budget/dashboard.html")
        self.assertIn("member", response.context)
        self.assertEqual(response.context["member"], self.member)
        self.assertTrue(len(response.context["accounts_data"]) > 0)

    def test_dashboard_view_without_active_member(self) -> None:
        """Vérifie que le dashboard ne plante pas si aucun membre n'est actif."""
        # On désactive le seul membre existant
        self.member.is_active = False
        self.member.save()

        url = reverse("dashboard")
        response = self.client.get(url)

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
