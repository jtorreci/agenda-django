"""Fail-closed settings for Docker production deployments.

The app is published behind the shared garnocex Caddy proxy under a path prefix
(see the garnocex-proxy CONTRACT.md): Caddy strips ``/agenda`` before proxying,
so Django must re-add it to every URL it emits via ``FORCE_SCRIPT_NAME``.
"""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403


DEFAULT_SCRIPT_NAME = "/agenda"
DEFAULT_ALLOWED_HOSTS = "garnocex.unex.es"
DEFAULT_CSRF_TRUSTED_ORIGINS = "https://garnocex.unex.es"


def required_setting(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured for production.")
    return value


def list_setting(name, default):
    """Comma-separated list from the environment; blank or unset uses the default."""
    raw = os.environ.get(name, "").strip() or default
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ImproperlyConfigured(f"{name} must contain at least one value.")
    return values


def script_name_setting():
    """URL prefix the proxy mounts the app under.

    Blank or unset uses DEFAULT_SCRIPT_NAME. An explicit "/" serves the app from
    the domain root, e.g. while a root-mounted proxy is still in use. Returns the
    prefix without a trailing slash ("" for the root).
    """
    raw = os.environ.get("DJANGO_SCRIPT_NAME", "").strip() or DEFAULT_SCRIPT_NAME
    if not raw.startswith("/") or "//" in raw or any(char in raw for char in "?#"):
        raise ImproperlyConfigured(
            "DJANGO_SCRIPT_NAME must be an absolute path such as /agenda, or / for the root."
        )
    return raw.rstrip("/")


if os.environ.get("DJANGO_DEBUG", "").lower() not in {"false", "0", "no"}:
    raise ImproperlyConfigured("DJANGO_DEBUG must be explicitly set to False in production.")

DEBUG = False
SECRET_KEY = required_setting("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = list_setting("ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS = list_setting("CSRF_TRUSTED_ORIGINS", DEFAULT_CSRF_TRUSTED_ORIGINS)

# ---- URL prefix -----------------------------------------------------------
# Every prefixed setting derives from SCRIPT_NAME so they cannot drift apart.
SCRIPT_NAME = script_name_setting()
FORCE_SCRIPT_NAME = SCRIPT_NAME or None
STATIC_URL = f"{SCRIPT_NAME}/static/"
MEDIA_URL = f"{SCRIPT_NAME}/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Scope cookies to the prefix so apps sharing the domain never see them.
COOKIE_PATH = SCRIPT_NAME or "/"
SESSION_COOKIE_PATH = COOKIE_PATH
CSRF_COOKIE_PATH = COOKIE_PATH
LANGUAGE_COOKIE_PATH = COOKIE_PATH

# WhiteNoise matches request.path_info, which never contains the script name.
# Its own default strips the prefix using get_script_prefix() at middleware
# initialisation, but get_wsgi_application() calls django.setup(set_prefix=False),
# so under Gunicorn that prefix is still "/" and the default would be
# "/agenda/static/", which never matches. Pin the path_info-relative prefix.
WHITENOISE_STATIC_PREFIX = "/static/"

# ---- Proxy and transport security -----------------------------------------
# The proxy terminates TLS and sets X-Forwarded-Proto from the real scheme.
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# The proxy forwards the original Host header unchanged, so X-Forwarded-Host is
# not needed; not trusting it removes one client-influenced input.
USE_X_FORWARDED_HOST = False
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
