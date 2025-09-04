from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from .models import CustomUser
from academics.models import Asignatura
from django.contrib.auth import get_user_model

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Permitir múltiples usuarios con el mismo email
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

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
        active_users = UserModel._default_manager.filter(
            username__iexact=email,
            is_active=True
        )
        return (u for u in active_users if u.has_usable_password())
