from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models.account import Household, HouseholdInvitation, HouseholdMember

User = get_user_model()


class HouseholdInvitationTestCase(TestCase):
    def setUp(self) -> None:
        self.user_maxime = User.objects.create_user(
            username="maxime", password="password123"
        )
        self.household = Household.objects.create(name="Foyer de Maxime")
        self.member_maxime = HouseholdMember.objects.create(
            name="Maxime", user=self.user_maxime, household=self.household
        )

        # Création d'une invitation valide
        self.invitation = HouseholdInvitation.objects.create(
            household=self.household, created_by=self.user_maxime
        )

    def test_anonymous_user_joining_saves_token_in_session(self) -> None:
        """
        Un visiteur clique sur le lien. Le token doit être sauvegardé dans
        sa session et il doit être redirigé vers l'inscription.
        """
        url = reverse("join_household", args=[self.invitation.token])
        response = self.client.get(url)

        self.assertRedirects(response, reverse("register"))
        self.assertEqual(
            self.client.session.get("invite_token"), str(self.invitation.token)
        )

    def test_registration_with_invite_token(self) -> None:
        """
        Lors de l'inscription, si un token est dans la session,
        l'utilisateur rejoint le foyer invité au lieu d'en créer un nouveau.
        """
        # On simule le clic précédent en injectant le token dans la session
        session = self.client.session
        session["invite_token"] = str(self.invitation.token)
        session.save()

        data = {
            "username": "laurie_new",
            "email": "laurie@budget.local",
            "password": "SuperPassword123!",
            "password_confirm": "SuperPassword123!",
        }
        self.client.post(reverse("register"), data)

        new_user = User.objects.get(username="laurie_new")
        new_member = HouseholdMember.objects.get(user=new_user)

        # Elle a bien rejoint le foyer de Maxime !
        self.assertEqual(new_member.household, self.household)

        # Le nombre total de foyers n'a pas augmenté (1 seul foyer)
        self.assertEqual(Household.objects.count(), 1)

    def test_authenticated_user_joining_get_confirmation(self) -> None:
        """Un utilisateur connecté clique sur le lien, il doit voir la demande de confirmation."""
        user_laurie = User.objects.create_user(
            username="laurie", password="password123"
        )
        self.client.force_login(user_laurie)

        url = reverse("join_household", args=[self.invitation.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/invite_confirm.html")

    def test_authenticated_user_joining_post(self) -> None:
        """L'utilisateur confirme vouloir rejoindre le foyer via POST."""
        user_laurie = User.objects.create_user(
            username="laurie", password="password123"
        )
        member_laurie = HouseholdMember.objects.create(
            name="Laurie",
            user=user_laurie,
            household=Household.objects.create(name="Foyer temporaire"),
        )
        self.client.force_login(user_laurie)

        url = reverse("join_household", args=[self.invitation.token])
        response = self.client.post(url)  # <--- On valide l'invitation (POST)

        self.assertRedirects(response, reverse("dashboard"))

        member_laurie.refresh_from_db()
        self.assertEqual(member_laurie.household, self.household)

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.accepted_by, user_laurie)

    def test_invalid_invitation_renders_error_template(self) -> None:
        """Une invitation expirée ou déjà acceptée doit afficher le template d'erreur."""
        self.invitation.accepted_by = self.user_maxime
        self.invitation.save()

        url = reverse("join_household", args=[self.invitation.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "registration/invite_error.html")
