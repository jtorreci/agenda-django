from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from .models import LoginAttempt
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or '0.0.0.0'

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    try:
        LoginAttempt.objects.create(
            username=user.username,
            ip_address=get_client_ip(request),
            success=True
        )
    except Exception as e:
        logger.error(f"Error logging successful login attempt: {e}")

@receiver(user_login_failed)
def user_login_failed_handler(sender, credentials, request, **kwargs):
    try:
        username = credentials.get('username', 'unknown')
        if username and len(username) > 150:
            username = username[:150]
        LoginAttempt.objects.create(
            username=username,
            ip_address=get_client_ip(request),
            success=False
        )
    except Exception as e:
        logger.error(f"Error logging failed login attempt: {e}")
