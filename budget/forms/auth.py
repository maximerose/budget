from typing import ClassVar

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        error_messages={"invalid": "Saisissez une adresse e-mail valide."},
    )
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields: ClassVar[dict[str, str]] = ["username", "email"]
        error_messages: ClassVar[dict[str, dict[str, str]]] = {
            "username": {
                "unique": "Un utilisateur avec ce nom d'utilisateur existe déjà."
            }
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error(
                "password_confirm", "Les deux mots de passe ne correspondent pas."
            )
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
