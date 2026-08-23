from django.test import TestCase

from budget.models import HouseholdMember


class CoreModelsTestCase(TestCase):
    def test_base_model_fields_auto_generation(self) -> None:
        """Valide la génération de l'UUID et l'hydratation des dates (BaseModel)."""
        member = HouseholdMember.objects.create(name="Testeur Core")

        # L'ID doit être généré automatiquement (UUID)
        self.assertIsNotNone(member.id)

        # Les dates de création et de mise à jour doivent être remplies
        self.assertIsNotNone(member.created_at)
        self.assertIsNotNone(member.updated_at)

    def test_soft_delete_model_default_behavior(self) -> None:
        """Valide le comportement par défaut de SoftDeleteModel."""
        member = HouseholdMember.objects.create(name="Testeur SoftDelete")

        # Par défaut, une entité doit être active
        self.assertTrue(member.is_active)
