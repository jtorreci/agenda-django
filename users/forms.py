from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from .models import CustomUser
from academics.models import Asignatura
from django.contrib.auth import get_user_model

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email',)

class NotificationForm(forms.Form):
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)

class StudentSubjectForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ['subjects']

class PasswordResetByUsernameForm(PasswordResetForm):
    """
    Formulario para el reseteo de contraseña que busca por username en lugar de email.
    """
    # Sobrescribimos el campo email para pedir el nombre de usuario.
    # Mantenemos el nombre del campo 'email' porque la clase padre lo espera.
    email = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        widget=forms.TextInput(attrs={'autocomplete': 'username'})
    )

    def get_users(self, email):
        """
        Sobrescribe el método original que busca por email.
        Ahora busca por username (que se pasa en la variable 'email').
        """
        UserModel = get_user_model()
        return UserModel._default_manager.filter(username__iexact=email)
