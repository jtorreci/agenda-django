from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from .models import LoginAttempt

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    LoginAttempt.objects.create(
        username=user.username,
        ip_address=get_client_ip(request),
        success=True
    )

@receiver(user_login_failed)
def user_login_failed_handler(sender, credentials, request, **kwargs):
    LoginAttempt.objects.create(
        username=credentials.get('username'),
        ip_address=get_client_ip(request),
        success=False
    )
