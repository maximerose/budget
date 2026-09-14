import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import Error as DatabaseError
from django.test import TestCase
from django.urls import reverse

from budget.models.account import Household, HouseholdMember
from budget.models.category import Category, CategoryType

User = get_user_model()


class ApiViewsTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="maxime", password="password123")
        self.household = Household.objects.create(name="Foyer Test")
        self.member = HouseholdMember.objects.create(
            name="Maxime",
            household=self.household,
            user=self.user,
        )
        self.url = reverse("api_create_element")

    def test_api_requires_login(self) -> None:
        """Vérifie que l'API est protégée contre les utilisateurs non connectés."""
        response = self.client.post(self.url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, 302)

    def test_api_requires_post_method(self) -> None:
        """Vérifie que l'API rejette les requêtes GET."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"], "Méthode non autorisée")

    def test_api_invalid_json(self) -> None:
        """Vérifie le comportement si le payload n'est pas du JSON valide."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data="ceci_nest_pas_du_json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Format JSON invalide")

    def test_api_missing_data(self) -> None:
        """Vérifie le comportement si le type ou la valeur est manquant."""
        self.client.force_login(self.user)
        payload = {"type": "category"}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Données invalides")

    def test_api_unknown_type(self) -> None:
        """Vérifie le comportement si le type demandé est inconnu."""
        self.client.force_login(self.user)
        payload = {"type": "vaisseau_spatial", "value": "Faucon Millenium"}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Type inconnu")

    def test_api_create_category_success(self) -> None:
        """Vérifie la création réussie d'une catégorie à la volée."""
        self.client.force_login(self.user)
        payload = {"type": "category", "value": "  Nouveau Resto  "}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["text"], "Nouveau Resto")

        category = Category.objects.get(id=data["id"])
        self.assertEqual(category.name, "Nouveau Resto")

    def test_api_create_category_duplicate_name(self) -> None:
        """Vérifie que l'API refuse la création si le nom existe déjà."""
        Category.objects.create(
            name="Courses", type=CategoryType.VARIABLE, household=self.household
        )
        self.client.force_login(self.user)

        payload = {"type": "category", "value": "Courses"}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        # Le statut 400 doit être renvoyé avec notre message d'erreur
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Cette catégorie existe déjà.")
        # La DB ne doit contenir qu'une seule catégorie "Courses"
        self.assertEqual(Category.objects.count(), 1)

    @patch("budget.views.api.Category.objects.create")
    def test_api_create_category_validation_error(self, mock_create) -> None:
        """Simule une ValidationError pour vérifier que le bloc 'except' de la vue l'attrape bien."""
        self.client.force_login(self.user)
        mock_create.side_effect = ValidationError(["Une erreur métier est survenue."])

        payload = {"type": "category", "value": "Test"}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Erreur de validation: Une erreur métier est survenue.",
        )

    @patch("budget.views.api.Category.objects.create")
    def test_api_create_category_database_error(self, mock_create) -> None:
        """Simule un plantage BDD (DatabaseError) pour vérifier la sécurité de la vue."""
        self.client.force_login(self.user)
        mock_create.side_effect = DatabaseError("Serveur SQL hors ligne")

        payload = {"type": "category", "value": "Test"}
        response = self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["error"],
            "Erreur lors de l'enregistrement en base de données",
        )
