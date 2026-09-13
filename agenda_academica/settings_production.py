"""Fail-closed settings for Docker production deployments."""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403


def required_setting(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured for production.")
    return value


if os.environ.get("DJANGO_DEBUG", "").lower() not in {"false", "0", "no"}:
    raise ImproperlyConfigured("DJANGO_DEBUG must be explicitly set to False in production.")

DEBUG = False
SECRET_KEY = required_setting("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [host.strip() for host in required_setting("ALLOWED_HOSTS").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in required_setting("CSRF_TRUSTED_ORIGINS").split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
