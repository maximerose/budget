from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models.account import HouseholdMember

User = get_user_model()


class AuthenticationTestCase(TestCase):
    def test_login_page_renders(self) -> None:
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_register_page_renders(self) -> None:
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/register.html")

    def test_successful_registration_creates_household_and_member(self) -> None:
        url = reverse("register")
        data = {
            "username": "nouveau_testeur",
            "email": "testeur@budget.local",
            "password": "SuperPassword123!",  
            "password_confirm": "SuperPassword123!",
        }

        response = self.client.post(url, data)
        self.assertRedirects(
            response, reverse("login")
        )  # Redirige bien au login par défaut

        self.assertTrue(User.objects.filter(username="nouveau_testeur").exists())
        new_user = User.objects.get(username="nouveau_testeur")

        self.assertTrue(HouseholdMember.objects.filter(user=new_user).exists())
        new_member = HouseholdMember.objects.get(user=new_user)
        self.assertEqual(new_member.name, "nouveau_testeur")
        self.assertIsNotNone(new_member.household)

    def test_register_password_mismatch(self) -> None:
        url = reverse("register")
        data = {
            "username": "testeur2",
            "email": "testeur2@budget.local",
            "password": "SuperPassword123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        # NOUVELLE SYNTAXE DJANGO 5+ POUR LES FORMULAIRES
        self.assertFormError(
            response.context["form"],
            "password_confirm",
            "Les deux mots de passe ne correspondent pas.",
        )
        self.assertFalse(User.objects.filter(username="testeur2").exists())

    def test_register_invalid_email(self) -> None:
        url = reverse("register")
        data = {
            "username": "testeur3",
            "email": "not-an-email",
            "password": "SuperPassword123!",
            "password_confirm": "SuperPassword123!",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "email", "Saisissez une adresse e-mail valide."
        )

    def test_register_duplicate_username(self) -> None:
        User.objects.create_user(username="existant", password="password123")
        url = reverse("register")
        data = {
            "username": "existant",
            "email": "nouveau@budget.local",
            "password": "SuperPassword123!",
            "password_confirm": "SuperPassword123!",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "username",
            "Un utilisateur avec ce nom d'utilisateur existe déjà.",
        )

    def test_user_login_redirects_to_dashboard(self) -> None:
        user = User.objects.create_user(username="maxime", password="password123")
        # On lui crée son profil membre pour qu'il ait accès au Dashboard !
        HouseholdMember.objects.create(name="Maxime", user=user)

        url = reverse("login")
        response = self.client.post(
            url, {"username": "maxime", "password": "password123"}
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_dashboard_displays_correct_logged_in_user(self) -> None:
        user1 = User.objects.create_user(username="maxime", password="password123")
        member1 = HouseholdMember.objects.create(name="Maxime", user=user1)

        user2 = User.objects.create_user(username="laurie", password="password123")
        member2 = HouseholdMember.objects.create(name="Laurie", user=user2)

        self.client.login(username="laurie", password="password123")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["member"], member2)
        self.assertNotEqual(response.context["member"], member1)
