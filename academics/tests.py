from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import AcademicYear, Asignatura, SubjectOffering, Titulacion


class AcademicYearActivationTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            code='2026-27',
            starts_on=date(2026, 9, 1),
            ends_on=date(2027, 8, 31),
        )
        self.plan = Titulacion.objects.create(
            nombre='Degree in Computing',
            codigo_plan='COMP-2026',
        )
        self.subject = Asignatura.objects.create(
            nombre='Programming I',
            codigo_asignatura='COMP101',
            titulacion=self.plan,
            curso=1,
            semestre=1,
        )

    def test_draft_year_cannot_activate_with_incomplete_offering(self):
        SubjectOffering.objects.create(academic_year=self.year, subject=self.subject)

        with self.assertRaises(ValidationError):
            self.year.activate()

        self.year.refresh_from_db()
        self.assertEqual(self.year.state, AcademicYear.STATE_DRAFT)

    def test_year_activates_when_every_offering_has_curriculum_metadata(self):
        SubjectOffering.objects.create(
            academic_year=self.year,
            subject=self.subject,
            curricular_year=1,
            semester=1,
        )

        self.year.activate()

        self.year.refresh_from_db()
        self.assertEqual(self.year.state, AcademicYear.STATE_ACTIVE)
