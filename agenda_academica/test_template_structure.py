"""Structural checks for templates that extend base.html.

Django silently discards anything a child template places outside a block, and a
block the parent does not define is never rendered. Both mistakes have shipped
before (dashboard activity modals and the iCal management script), so every
child template is checked here.
"""
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.template.loader_tags import BlockNode, ExtendsNode
from django.template.base import TextNode
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from academics.models import Titulacion
from users.models import CustomUser

BASE_TEMPLATE = "base.html"


def _template_names():
    """Template names (relative to their templates/ dir) across project and apps."""
    roots = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    roots += sorted(Path(settings.BASE_DIR).glob("*/templates"))
    names = set()
    for root in roots:
        for path in root.rglob("*.html"):
            names.add(path.relative_to(root).as_posix())
    return sorted(names)


class ChildTemplateStructureTests(SimpleTestCase):
    def setUp(self):
        engine = engines["django"]
        self.engine = engine
        base = engine.get_template(BASE_TEMPLATE).template
        self.base_blocks = {node.name for node in base.nodelist.get_nodes_by_type(BlockNode)}

    def child_templates(self):
        for name in _template_names():
            template = self.engine.get_template(name).template
            extends = [node for node in template.nodelist if isinstance(node, ExtendsNode)]
            if extends and extends[0].parent_name.var == BASE_TEMPLATE:
                yield name, extends[0]

    def test_there_are_child_templates_to_check(self):
        self.assertGreater(len(list(self.child_templates())), 10)

    def test_no_content_outside_blocks(self):
        for name, extends in self.child_templates():
            with self.subTest(template=name):
                stray = [
                    node.s.strip()[:80]
                    for node in extends.nodelist
                    if isinstance(node, TextNode) and node.s.strip()
                ]
                self.assertEqual(stray, [], f"{name} has markup outside any block; Django drops it")

    def test_only_blocks_defined_by_base(self):
        for name, extends in self.child_templates():
            with self.subTest(template=name):
                unknown = set(extends.blocks) - self.base_blocks
                self.assertEqual(unknown, set(), f"{name} uses blocks that {BASE_TEMPLATE} never renders")


class RenderedFixesTests(TestCase):
    password = "structure-test-password-1"

    @classmethod
    def setUpTestData(cls):
        cls.coordinator = CustomUser.objects.create_user(
            username="structure_coordinator",
            email="structure_coordinator@unex.es",
            password=cls.password,
            role=CustomUser.ROLE_COORDINATOR,
        )
        cls.student = CustomUser.objects.create_user(
            username="structure_student",
            email="structure_student@alumnos.unex.es",
            password=cls.password,
            role=CustomUser.ROLE_STUDENT,
        )
        Titulacion.objects.create(nombre="Grado de prueba", coordinador=cls.coordinator)

    def test_dashboards_render_activity_detail_modal(self):
        for user, url in (
            (self.coordinator, reverse("coordinator_dashboard")),
            (self.student, reverse("student_dashboard")),
        ):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="activityDetailModal"')
                self.assertContains(response, 'id="modalActivityTitle"')
                self.client.logout()

    def test_ical_management_renders_its_script(self):
        self.client.force_login(self.coordinator)
        response = self.client.get(reverse("ical_management"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "function createAutomaticFeeds()")
        self.assertContains(response, "function copyToClipboard(button)")

    def test_create_automatic_icals_requires_post(self):
        self.client.force_login(self.coordinator)
        url = reverse("create_automatic_icals")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertGreaterEqual(response.json()["created"], 1)
