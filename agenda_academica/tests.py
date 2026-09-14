"""Regression tests for serving the app under a URL prefix behind a proxy.

The shared garnocex Caddy proxy strips ``/agenda`` before proxying, and root paths
such as ``/login/`` return 404 there by design. Every URL the app emits must
therefore carry the prefix. The test client reproduces the proxy: request paths
are the stripped ``PATH_INFO``, ``FORCE_SCRIPT_NAME`` supplies the prefix, and the
script prefix is set as Django's WSGIHandler does per request.
"""
import importlib
import os
import re
import sys
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import clear_script_prefix, reverse, set_script_prefix

from users.models import CustomUser

PREFIX = "/agenda"

# Root-relative URLs in markup or inline JS that do not start with the prefix.
# "//" (protocol-relative) is excluded; "#" anchors and relative URLs never match.
# The bare prefix ("/agenda", e.g. the admin "View site" link) is allowed.
UNPREFIXED_URL = re.compile(
    r"""(?:
        \b(?:href|action|src|formaction|data-url)\s*=\s*["']
      | \bfetch\(\s*[`"']
      | \blocation(?:\.href)?\s*=\s*[`"']
      | \burl\s*:\s*[`"']
    )/(?!/|agenda(?![\w-]))""",
    re.VERBOSE,
)


def unprefixed_urls(html):
    return [
        html[max(match.start() - 40, 0):match.end() + 40]
        for match in UNPREFIXED_URL.finditer(html)
    ]


@override_settings(
    FORCE_SCRIPT_NAME=PREFIX,
    STATIC_URL=f"{PREFIX}/static/",
    MEDIA_URL=f"{PREFIX}/media/",
    SESSION_COOKIE_PATH=PREFIX,
    CSRF_COOKIE_PATH=PREFIX,
    LANGUAGE_COOKIE_PATH=PREFIX,
    SECURE_SSL_REDIRECT=False,
)
class PrefixedUrlsTests(TestCase):
    password = "prefix-test-password-1"

    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: CustomUser.objects.create_user(
                username=f"prefix_{role.lower()}",
                email=f"prefix_{role.lower()}@unex.es",
                password=cls.password,
                role=role,
            )
            for role in (
                CustomUser.ROLE_STUDENT,
                CustomUser.ROLE_TEACHER,
                CustomUser.ROLE_COORDINATOR,
                CustomUser.ROLE_ADMIN,
            )
        }
        cls.superuser = CustomUser.objects.create_superuser(
            username="prefix_superuser",
            email="prefix_superuser@unex.es",
            password=cls.password,
        )

    def setUp(self):
        # WSGIHandler sets the thread-local script prefix from FORCE_SCRIPT_NAME on
        # every request, but the test client does not, so mirror it here.
        set_script_prefix(PREFIX)
        self.addCleanup(clear_script_prefix)

    def assert_page_is_prefixed(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, f"GET {path}")
        self.assertEqual(
            unprefixed_urls(response.content.decode()),
            [],
            f"{path} emits URLs without the {PREFIX}/ prefix",
        )

    def assert_redirects_under_prefix(self, response):
        self.assertIn(response.status_code, (301, 302))
        self.assertTrue(
            response["Location"].startswith(f"{PREFIX}/"),
            f"Location {response['Location']!r} is not under {PREFIX}/",
        )

    def test_reverse_includes_prefix(self):
        response = self.client.get("/login/")
        self.assertEqual(response.wsgi_request.path, f"{PREFIX}/login/")
        self.assertEqual(reverse("login"), f"{PREFIX}/login/")

    def test_anonymous_pages_are_prefixed(self):
        for path in (
            "/",
            "/login/",
            "/users/register/",
            "/users/resend_activation/",
            "/users/password_reset/",
            "/logout_success/",
            "/admin/login/",
        ):
            with self.subTest(path=path):
                self.assert_page_is_prefixed(path)

    def test_role_dashboards_are_prefixed(self):
        dashboards = {
            CustomUser.ROLE_STUDENT: "/users/student_dashboard/",
            CustomUser.ROLE_TEACHER: "/users/teacher_dashboard/",
            CustomUser.ROLE_COORDINATOR: "/users/coordinator_dashboard/",
            CustomUser.ROLE_ADMIN: "/users/admin_dashboard/",
        }
        for role, path in dashboards.items():
            with self.subTest(role=role):
                self.client.force_login(self.users[role])
                self.assert_page_is_prefixed(path)
                self.client.logout()

    def test_catalogue_import_pages_are_prefixed(self):
        from datetime import date

        from academics.catalogue_import import build_draft, parse_catalogue
        from academics.models import AcademicYear

        year = AcademicYear.objects.create(
            code="2026-27", starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31)
        )
        rows, errors = parse_catalogue(
            b"plan_code;plan_name;subject_code;subject_name;curricular_year;semester\n"
            b"P1;Plan One;S1;Subject One;1;1\n"
        )
        self.assertEqual(errors, [])
        draft = build_draft(year, rows, "catalogue.csv", self.users[CustomUser.ROLE_ADMIN])

        self.client.force_login(self.users[CustomUser.ROLE_ADMIN])
        self.assert_page_is_prefixed("/catalogue/imports/")
        self.assert_page_is_prefixed(f"/catalogue/imports/{draft.pk}/")
        self.assertEqual(
            reverse("catalogue_import_detail", args=[draft.pk]),
            f"{PREFIX}/catalogue/imports/{draft.pk}/",
        )

        response = self.client.post(f"/catalogue/imports/years/{year.pk}/activate/")
        self.assert_redirects_under_prefix(response)

    def test_admin_index_is_prefixed(self):
        self.client.force_login(self.superuser)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{PREFIX}/static/admin/css/base.css"')
        self.assertEqual(unprefixed_urls(response.content.decode()), [])

    def test_login_required_redirects_under_prefix(self):
        response = self.client.get("/users/teacher_dashboard/")
        self.assert_redirects_under_prefix(response)
        self.assertEqual(
            response["Location"],
            f"{PREFIX}/login/?next={PREFIX}/users/teacher_dashboard/",
        )

    def test_login_flow_redirects_and_cookies_under_prefix(self):
        response = self.client.post(
            "/login/",
            {"username": "prefix_teacher", "password": self.password},
        )
        self.assert_redirects_under_prefix(response)
        self.assertEqual(response["Location"], f"{PREFIX}/users/dashboard_redirect/")
        self.assertEqual(response.cookies["sessionid"]["path"], PREFIX)

        response = self.client.get("/users/dashboard_redirect/")
        self.assertEqual(response["Location"], f"{PREFIX}/users/teacher_dashboard/")

        response = self.client.post("/logout/")
        self.assertEqual(response["Location"], f"{PREFIX}/logout_success/")

    def test_ical_links_are_absolute_and_prefixed(self):
        self.client.force_login(self.users[CustomUser.ROLE_ADMIN])
        response = self.client.get("/ical/management/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["base_url"], "https://testserver")

    def test_detector_catches_root_paths(self):
        self.assertTrue(unprefixed_urls('<a href="/admin/">'))
        self.assertTrue(unprefixed_urls("fetch(`/ajax/x/`)"))
        self.assertTrue(unprefixed_urls("window.location.href = '/activity/1/'"))
        self.assertFalse(unprefixed_urls('<a href="/agenda/admin/">'))
        self.assertFalse(unprefixed_urls('<a href="/agenda">'))
        self.assertTrue(unprefixed_urls('<a href="/agenda-old/">'))
        self.assertFalse(unprefixed_urls('<script src="//cdn.example.com/x.js">'))
        self.assertFalse(unprefixed_urls('<a href="#top">'))


class ProductionSettingsTests(SimpleTestCase):
    module_name = "agenda_academica.settings_production"
    base_env = {"DJANGO_DEBUG": "False", "DJANGO_SECRET_KEY": "test-only-secret"}

    def load(self, **env):
        sys.modules.pop(self.module_name, None)
        self.addCleanup(sys.modules.pop, self.module_name, None)
        with mock.patch.dict(os.environ, {**self.base_env, **env}, clear=True):
            return importlib.import_module(self.module_name)

    def test_defaults_mount_the_app_under_agenda(self):
        settings = self.load()
        self.assertEqual(settings.FORCE_SCRIPT_NAME, "/agenda")
        self.assertEqual(settings.STATIC_URL, "/agenda/static/")
        self.assertEqual(settings.MEDIA_URL, "/agenda/media/")
        self.assertEqual(settings.SESSION_COOKIE_PATH, "/agenda")
        self.assertEqual(settings.CSRF_COOKIE_PATH, "/agenda")
        self.assertEqual(settings.LANGUAGE_COOKIE_PATH, "/agenda")
        self.assertEqual(settings.WHITENOISE_STATIC_PREFIX, "/static/")
        self.assertEqual(settings.ALLOWED_HOSTS, ["garnocex.unex.es"])
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, ["https://garnocex.unex.es"])
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertFalse(settings.USE_X_FORWARDED_HOST)
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.LOGIN_URL, "login")
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "dashboard_redirect")

    def test_blank_env_values_use_defaults(self):
        settings = self.load(ALLOWED_HOSTS="", CSRF_TRUSTED_ORIGINS=" ", DJANGO_SCRIPT_NAME="")
        self.assertEqual(settings.ALLOWED_HOSTS, ["garnocex.unex.es"])
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, ["https://garnocex.unex.es"])
        self.assertEqual(settings.FORCE_SCRIPT_NAME, "/agenda")

    def test_environment_overrides(self):
        settings = self.load(
            DJANGO_SCRIPT_NAME="/pruebas/",
            ALLOWED_HOSTS="localhost, 127.0.0.1",
            CSRF_TRUSTED_ORIGINS="https://localhost:8443",
        )
        self.assertEqual(settings.FORCE_SCRIPT_NAME, "/pruebas")
        self.assertEqual(settings.STATIC_URL, "/pruebas/static/")
        self.assertEqual(settings.MEDIA_URL, "/pruebas/media/")
        self.assertEqual(settings.SESSION_COOKIE_PATH, "/pruebas")
        self.assertEqual(settings.ALLOWED_HOSTS, ["localhost", "127.0.0.1"])
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, ["https://localhost:8443"])

    def test_root_script_name_disables_the_prefix(self):
        settings = self.load(DJANGO_SCRIPT_NAME="/")
        self.assertIsNone(settings.FORCE_SCRIPT_NAME)
        self.assertEqual(settings.STATIC_URL, "/static/")
        self.assertEqual(settings.SESSION_COOKIE_PATH, "/")

    def test_fails_closed(self):
        for env in (
            {"DJANGO_SCRIPT_NAME": "agenda"},
            {"DJANGO_SCRIPT_NAME": "//evil.example"},
            {"ALLOWED_HOSTS": ","},
            {"DJANGO_SECRET_KEY": ""},
            {"DJANGO_DEBUG": "True"},
        ):
            with self.subTest(env=env), self.assertRaises(ImproperlyConfigured):
                self.load(**env)


class WhiteNoisePrefixTests(SimpleTestCase):
    """WhiteNoise must serve static files at the stripped path under Gunicorn."""

    def serve(self, **settings):
        from whitenoise.middleware import WhiteNoiseMiddleware

        # get_wsgi_application() calls django.setup(set_prefix=False), so the
        # script prefix is still "/" when Gunicorn instantiates the middleware.
        clear_script_prefix()
        self.addCleanup(clear_script_prefix)
        with override_settings(
            FORCE_SCRIPT_NAME=PREFIX,
            STATIC_URL=f"{PREFIX}/static/",
            STATIC_ROOT=None,
            WHITENOISE_USE_FINDERS=True,
            WHITENOISE_AUTOREFRESH=True,
            **settings,
        ):
            middleware = WhiteNoiseMiddleware(lambda request: None)
            request = RequestFactory().get("/static/admin/css/base.css")
            return middleware.static_prefix, middleware(request)

    def test_production_static_prefix_serves_stripped_paths(self):
        static_prefix, response = self.serve(WHITENOISE_STATIC_PREFIX="/static/")
        self.assertEqual(static_prefix, "/static/")
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=\"utf-8\"")

    def test_default_static_prefix_misses_under_wsgi(self):
        from django.conf import settings

        self.assertFalse(hasattr(settings, "WHITENOISE_STATIC_PREFIX"))
        static_prefix, response = self.serve()
        self.assertEqual(static_prefix, f"{PREFIX}/static/")
        self.assertIsNone(response)
