from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.contrib import messages

UserModel = get_user_model()

class EmailVerificationBackend(ModelBackend):
    """
    Custom authentication backend that checks if user's email is verified (is_active)
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to get user by username
            user = UserModel.objects.get(username=username)
            
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
                
                # Everything is OK
                return user
            
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user
            UserModel().set_password(password)
        
        return None
    
    def get_user(self, user_id):
        try:
            user = UserModel.objects.get(pk=user_id)
            return user if user.is_active else None
        except UserModel.DoesNotExist:
            return None