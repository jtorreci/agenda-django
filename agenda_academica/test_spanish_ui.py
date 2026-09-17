"""Regression tests: the user interface is Spanish only.

The app used to mix English and Spanish (LocaleMiddleware plus an incomplete
translation catalogue). These tests render the main pages for every role, with a
browser asking for English, and fail when common English UI words appear as
visible text.

What counts as visible text:
* HTML text nodes outside <script>, <style> and comments;
* user-facing attributes: title, placeholder, aria-label, alt, and the value of
  button-like inputs;
* inline JavaScript string literals that contain whitespace (prose such as alert
  messages, button labels and dynamically built HTML, whose tags are stripped).
  Literals passed to console.* and single-token literals (event names, CSS
  selectors, HTTP headers such as 'Content-Type') are ignored.

ENGLISH_WORDS is matched case-sensitively on word boundaries. Words that are also
valid Spanish UI text ("No", "Error", "Evaluable", "Total", "General") are left
out on purpose to avoid false positives.
"""
import re
from datetime import date
from html.parser import HTMLParser

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from academics.catalogue_import import build_draft, parse_catalogue
from academics.models import AcademicYear, Asignatura, SubjectOffering, Titulacion
from schedule.ical_import import build_draft as build_ical_draft, parse_calendar
from schedule.models import Actividad, ActividadGrupo, LogActividad, TipoActividad, VistaCalendario
from users.models import CustomUser

ENGLISH_WORDS = (
    'Actions', 'Activities', 'Activity', 'Approved', 'Back', 'Calendar', 'Cancel',
    'Close', 'Confirm', 'Copy', 'Create', 'Dashboard', 'Date', 'Day', 'Delete',
    'Description', 'Download', 'Edit', 'End', 'Filter', 'Hide', 'History', 'Home',
    'Loading', 'Login', 'Logout', 'Month', 'Name', 'Pending', 'Please', 'Register',
    'Restore', 'Save', 'Search', 'Select', 'Settings', 'Show', 'Start', 'Status',
    'Student', 'Subject', 'Subjects', 'Submit', 'Teacher', 'Coordinator', 'Today',
    'Type', 'Update', 'Version', 'Week', 'Welcome', 'Yes', 'Your',
)
ENGLISH_WORD_RE = re.compile(r'\b(?:%s)\b' % '|'.join(ENGLISH_WORDS))

VISIBLE_ATTRIBUTES = {'title', 'placeholder', 'aria-label', 'alt'}
BUTTON_INPUT_TYPES = {'button', 'submit', 'reset'}
JS_STRING_RE = re.compile(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`")
JS_CONSOLE_RE = re.compile(r'console\.\w+\([^;\n]*')
TEMPLATE_EXPR_RE = re.compile(r'\$\{[^}]*\}')
TAG_RE = re.compile(r'<[^>]*>')


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self._skip = None
        self._script = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self._skip = tag
            self._script = []
            return
        for name in VISIBLE_ATTRIBUTES & attrs.keys():
            self.chunks.append(attrs[name] or '')
        if tag == 'input' and (attrs.get('type') or '').lower() in BUTTON_INPUT_TYPES:
            self.chunks.append(attrs.get('value') or '')

    def handle_endtag(self, tag):
        if tag == self._skip:
            if tag == 'script':
                self.chunks.extend(js_visible_strings(''.join(self._script)))
            self._skip = None

    def handle_data(self, data):
        if self._skip == 'script':
            self._script.append(data)
        elif self._skip is None:
            self.chunks.append(data)


def js_visible_strings(source):
    source = JS_CONSOLE_RE.sub('', source)
    source = re.sub(r'^\s*//.*$', '', source, flags=re.MULTILINE)
    strings = []
    for literal in JS_STRING_RE.findall(source):
        text = TEMPLATE_EXPR_RE.sub(' ', literal[1:-1])
        if not re.search(r'\S\s+\S', text):
            continue
        strings.append(TAG_RE.sub(' ', text))
    return strings


def english_words(html):
    parser = VisibleTextParser()
    parser.feed(html)
    parser.close()
    found = set()
    for chunk in parser.chunks:
        found.update(ENGLISH_WORD_RE.findall(chunk))
    return sorted(found)


class EnglishWordDetectorTests(SimpleTestCase):
    def test_flags_visible_english(self):
        self.assertEqual(english_words('<button>Save</button>'), ['Save'])
        self.assertEqual(english_words('<a title="Edit activity" href="#">x</a>'), ['Edit'])
        self.assertEqual(english_words('<input type="submit" value="Delete">'), ['Delete'])
        self.assertEqual(english_words("<script>alert('Activity not found');</script>"), ['Activity'])
        self.assertEqual(
            english_words('<script>el.innerHTML = `<th>Start Date</th>`;</script>'), ['Date', 'Start']
        )

    def test_ignores_code_and_spanish(self):
        self.assertEqual(english_words('<button class="Save">Guardar</button>'), [])
        self.assertEqual(english_words("<script>headers: {'Content-Type': 'json'}</script>"), [])
        self.assertEqual(english_words("<script>console.error('Error loading activities:', e);</script>"), [])
        self.assertEqual(english_words('<style>.Today { color: red; }</style><!-- Save -->'), [])
        self.assertEqual(english_words('<p>No hay versiones. Versión actual. Evaluable: No</p>'), [])


class SpanishOnlyUiTests(TestCase):
    password = 'spanish-ui-password-1'

    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: CustomUser.objects.create_user(
                username=f'es_{role.lower()}', email=f'es_{role.lower()}@unex.es',
                password=cls.password, role=role,
            )
            for role in (CustomUser.ROLE_STUDENT, CustomUser.ROLE_TEACHER,
                         CustomUser.ROLE_COORDINATOR, CustomUser.ROLE_ADMIN)
        }
        cls.superuser = CustomUser.objects.create_superuser(
            username='es_superuser', email='es_superuser@unex.es', password=cls.password,
        )
        cls.year = AcademicYear.objects.create(
            code='2026-27', starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31), state='active',
        )
        cls.plan = Titulacion.objects.create(
            nombre='Grado en Ingeniería', codigo_plan='P1', coordinador=cls.users[CustomUser.ROLE_COORDINATOR],
        )
        cls.subject = Asignatura.objects.create(
            nombre='Cálculo', codigo_asignatura='S1', titulacion=cls.plan, curso=1, semestre=1,
        )
        SubjectOffering.objects.create(academic_year=cls.year, subject=cls.subject, curricular_year=1, semester=1)
        for role in (CustomUser.ROLE_STUDENT, CustomUser.ROLE_TEACHER, CustomUser.ROLE_COORDINATOR):
            cls.users[role].subjects.set([cls.subject])
        cls.users[CustomUser.ROLE_COORDINATOR].coordinated_titulaciones.set([cls.plan])

        start = timezone.make_aware(timezone.datetime(2026, 10, 7, 9))
        end = timezone.make_aware(timezone.datetime(2026, 10, 7, 11))
        cls.activity = Actividad.objects.create(
            nombre='Examen parcial', tipo_actividad=TipoActividad.objects.create(nombre='Examen'),
            academic_year=cls.year, fecha_inicio=start, fecha_fin=end, estado='visible',
            evaluable=True, porcentaje_evaluacion=20, descripcion='Temas 1 a 3',
        )
        cls.activity.asignaturas.set([cls.subject])
        ActividadGrupo.objects.create(actividad=cls.activity, nombre_grupo='A', fecha_inicio=start, fecha_fin=end)
        # Stored log types are historical English values; they must be displayed in Spanish.
        for tipo_log in ('Creation', 'Modification', 'Deletion', 'Version Restore'):
            LogActividad.objects.create(
                actividad=cls.activity, object_name=cls.activity.nombre, object_id=cls.activity.pk,
                usuario=cls.users[CustomUser.ROLE_TEACHER], tipo_log=tipo_log,
            )
        view = VistaCalendario.objects.create(nombre='Mi calendario', usuario=cls.users[CustomUser.ROLE_STUDENT])
        view.asignaturas.set([cls.subject])

        rows, errors = parse_catalogue(
            b'plan_code;plan_name;subject_code;subject_name;curricular_year;semester\n'
            b'P1;Plan uno;S1;Asignatura uno;1;1\n'
        )
        assert errors == []
        cls.draft = build_draft(cls.year, rows, 'catalogo.csv', cls.users[CustomUser.ROLE_ADMIN])

        cls.ical_draft = build_ical_draft(
            parse_calendar(
                'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Moodle//ES\r\n'
                'BEGIN:VEVENT\r\nUID:1@campusvirtual.example.org\r\nSUMMARY:Asistencia clases\r\n'
                'DESCRIPTION:Aula 1\r\nDTSTART:20261007T070000Z\r\nDTEND:20261007T090000Z\r\n'
                'CATEGORIES:99001\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
            ),
            cls.subject, cls.year, 'icalexport.ics', cls.users[CustomUser.ROLE_TEACHER],
        )

    def assert_spanish(self, path, status=200):
        response = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response.status_code, status, f'GET {path}')
        html = response.content.decode()
        # Django's own admin/search_form.html hard-codes the (untranslated) alt text
        # of the search icon; it is Django's markup, not the app's.
        html = html.replace('alt="Search"', 'alt=""')
        self.assertEqual(english_words(html), [], f'English UI words in {path}')

    def assert_pages_spanish(self, user, paths):
        if user is None:
            self.client.logout()
        else:
            self.client.force_login(user)
        for path in paths:
            with self.subTest(path=path, user=getattr(user, 'username', 'anonymous')):
                self.assert_spanish(path)

    def test_anonymous_pages(self):
        self.assert_pages_spanish(None, [
            '/', '/login/', '/users/register/', '/users/password_reset/',
            '/users/password_reset/done/', '/users/reset/done/', '/users/resend_activation/',
            '/logout_success/',
        ])

    def test_not_found_page(self):
        self.assert_spanish('/esta-pagina-no-existe/', status=404)

    def test_student_pages(self):
        self.assert_pages_spanish(self.users[CustomUser.ROLE_STUDENT], [
            '/users/student_dashboard/', '/users/select_subjects/', '/users/ical_config/',
            '/calendar_views/', '/calendar_views/new/',
        ])

    def test_teacher_pages(self):
        pk = self.activity.pk
        self.assert_pages_spanish(self.users[CustomUser.ROLE_TEACHER], [
            '/users/teacher_dashboard/', '/users/teacher_select_subjects/', '/users/teacher_student_view/',
            '/activity/unified/new/', f'/activity/unified/edit/{pk}/', '/activity/new/',
            f'/activity/edit/{pk}/', '/activity/multi-group/new/', f'/activity/view/{pk}/',
            f'/activity/{pk}/versions/', f'/activity/delete/{pk}/', '/activity/list/',
            '/ical/imports/', f'/ical/imports/{self.ical_draft.pk}/',
        ])

    def test_coordinator_pages(self):
        self.assert_pages_spanish(self.users[CustomUser.ROLE_COORDINATOR], [
            '/users/coordinator_dashboard/', '/activity/logs/', '/ical/management/',
            f'/activity/toggle_approval/{self.activity.pk}/', f'/activity/reactivate/{self.activity.pk}/',
        ])

    def test_admin_pages(self):
        self.assert_pages_spanish(self.users[CustomUser.ROLE_ADMIN], [
            '/users/admin_dashboard/', '/users/login_attempts/', '/users/kpi_report/',
            '/tipoactividad/', '/tipoactividad/create/', '/agenda_settings/',
            '/catalogue/imports/', f'/catalogue/imports/{self.draft.pk}/',
        ])

    def test_coordinator_dashboard_selection(self):
        self.client.force_login(self.users[CustomUser.ROLE_COORDINATOR])
        self.assert_spanish('/users/dashboard_redirect/')

    def test_django_admin(self):
        self.assert_pages_spanish(self.superuser, [
            '/admin/', '/admin/schedule/actividad/', f'/admin/schedule/actividad/{self.activity.pk}/change/',
            '/admin/users/customuser/', '/admin/academics/catalogueimport/',
        ])

    def test_accept_language_cannot_switch_django_messages_to_english(self):
        response = self.client.post(
            '/login/', {'username': 'nadie', 'password': 'incorrecta'}, HTTP_ACCEPT_LANGUAGE='en',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Please enter a correct')

    def test_stored_english_log_types_are_displayed_in_spanish(self):
        self.client.force_login(self.users[CustomUser.ROLE_ADMIN])
        response = self.client.get('/activity/logs/')
        for label in ('Creación', 'Modificación', 'Eliminación', 'Restauración de versión'):
            self.assertContains(response, label)
