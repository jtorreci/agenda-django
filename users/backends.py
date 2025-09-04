from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm

UserModel = get_user_model()

class EmailVerificationBackend(ModelBackend):
    """
    Custom authentication backend that checks if user's email is verified (is_active)
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        if username is None or password is None:
            return None
            
        try:
            # Try to get user by username (case insensitive)
            user = UserModel.objects.get(username__iexact=username)
            
            # Check if password is correct
            if user.check_password(password):
                # Check if user is active (email verified)
                if not user.is_active:
                    # User exists and password is correct but email not verified
                    if request:
                        messages.error(
                            request,
                            'Tu cuenta no está activada. Por favor, verifica tu correo electrónico antes de iniciar sesión. '
                            'Revisa tu bandeja de entrada y la carpeta de spam.'
                        )
                    return None
                
                # Everything is OK - return user for successful login
                return user
            else:
                # Password is incorrect - let Django handle the default error message
                return None
            
        except UserModel.DoesNotExist:
            # User doesn't exist - run password hasher to prevent timing attacks
            UserModel().set_password(password)
            return None
    
    def get_user(self, user_id):
        try:
            user = UserModel.objects.get(pk=user_id)
            return user if user.is_active else None
        except UserModel.DoesNotExist:
            return None