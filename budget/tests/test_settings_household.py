from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models.account import Household, HouseholdInvitation, HouseholdMember

User = get_user_model()


class SettingsHouseholdProfileTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="maxime",
            email="max@test.com",
            password="password123",
        )
        self.household = Household.objects.create(name="Foyer de Maxime")
        self.member = HouseholdMember.objects.create(
            name="Maxime",
            household=self.household,
            user=self.user,
        )
        self.client.force_login(self.user)

    def test_household_profile_view_renders(self) -> None:
        """Vérifie que l'onglet Foyer et Profil s'affiche bien."""
        url = reverse("settings_profile")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "budget/settings/profile_list.html")

    def test_update_household_name(self) -> None:
        """Vérifie la mise à jour du nom du foyer."""
        url = reverse("settings_household_update")
        data = {"name": "Le Super Foyer"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.household.refresh_from_db()
        self.assertEqual(self.household.name, "Le Super Foyer")

    def test_update_profile_info(self) -> None:
        """Vérifie la mise à jour du nom de membre et de l'email utilisateur."""
        url = reverse("settings_profile_update")
        data = {"name": "Maxou", "email": "maxou@test.com"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.member.name, "Maxou")
        self.assertEqual(self.user.email, "maxou@test.com")

    def test_generate_invitation_link(self) -> None:
        """Vérifie la génération d'un lien d'invitation."""
        url = reverse("settings_generate_invite")
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            HouseholdInvitation.objects.filter(
                household=self.household, created_by=self.user
            ).exists()
        )
