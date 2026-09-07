import re
from typing import ClassVar

from django import forms
from django.contrib.auth import get_user_model

from budget.models.account import HouseholdInvitation

User = get_user_model()


class RegisterForm(forms.ModelForm):
    display_name = forms.CharField(
        required=True,
        label="Nom d'affichage",
    )
    email = forms.EmailField(
        required=True,
        error_messages={"invalid": "Saisissez une adresse e-mail valide."},
    )
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)
    household_code = forms.CharField(
        required=False,
        help_text="Optionnel : Saisissez le code fourni par un membre de votre foyer.",
    )

    class Meta:
        model = User
        fields: ClassVar[dict[str, str]] = ["username", "email"]
        error_messages: ClassVar[dict[str, dict[str, str]]] = {
            "username": {
                "unique": "Un utilisateur avec ce nom d'utilisateur existe déjà."
            }
        }

    def clean_username(self):
        username = self.cleaned_data.get("username", "")
        username = username.strip().lower()
        if not re.match(r"^[a-z0-9-]+$", username):
            raise forms.ValidationError(
                "Le pseudo ne doit contenir que des lettres minuscules, des chiffres et des tirets."
            )
        return username

    def clean_display_name(self):
        name = self.cleaned_data.get("display_name", "")
        return name.strip().title()

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")

        if p1 and p2 and p1 != p2:
            self.add_error(
                "password_confirm", "Les deux mots de passe ne correspondent pas."
            )

        code = cleaned_data.get("household_code")
        if code:
            code = code.strip().upper()
            invitation = HouseholdInvitation.objects.filter(
                token=code, accepted_by__isnull=True
            ).first()

            if not invitation or not invitation.is_valid:
                self.add_error(
                    "household_code", "Ce Code Foyer est invalide ou a expiré."
                )
            else:
                # On stocke l'invitation valide pour l'utiliser dans la vue !
                cleaned_data["valid_invitation"] = invitation

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
