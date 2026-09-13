from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .catalogue_import import apply_import, build_draft, normalize_name, parse_catalogue
from .models import (
    AcademicYear,
    Asignatura,
    CatalogueImport,
    CatalogueImportRow,
    SubjectOffering,
    TeachingAssignment,
    Titulacion,
)


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


# ---------------------------------------------------------------------------
# Catalogue import
# ---------------------------------------------------------------------------

OFFICIAL_HEADER = (
    'Curso;codPlan;Plan de estudios;codAsignatura;Asignatura;Créditos de la asignatura;'
    'DNI profesor;Nombre profesor;Matriculados;Semestre\r\n'
)


def official_csv(*lines, bom=True):
    text = OFFICIAL_HEADER + ''.join(line + '\r\n' for line in lines)
    return (('﻿' if bom else '') + text).encode('utf-8')


def make_year(code='2026-27', state=AcademicYear.STATE_DRAFT):
    start = int(code[:4])
    return AcademicYear.objects.create(
        code=code, starts_on=date(start, 9, 1), ends_on=date(start + 1, 8, 31), state=state
    )


class CatalogueParserTests(TestCase):
    def test_official_export_with_bom_crlf_and_aliases(self):
        rows, errors = parse_catalogue(official_csv(
            '2024-25;1234;Grado en Ingeniería Informática;500001;Programación I;6,0;12345678Z;Ana López;120;1',
        ))

        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.plan_code, '1234')
        self.assertEqual(row.plan_name, 'Grado en Ingeniería Informática')
        self.assertEqual(row.subject_code, '500001')
        self.assertEqual(row.subject_name, 'Programación I')
        self.assertEqual(row.credits, Decimal('6.0'))
        self.assertEqual(row.semester, 1)

    def test_curso_column_is_academic_year_and_never_mapped(self):
        rows, errors = parse_catalogue(official_csv(
            '2024-25;1234;Plan;500001;Asig;6;X;Y;1;2',
        ))

        self.assertEqual(errors, [])
        self.assertIsNone(rows[0].curricular_year)

    def test_personal_columns_are_not_stored(self):
        rows, _ = parse_catalogue(official_csv('2024-25;1234;Plan;500001;Asig;6;12345678Z;Ana López;120;1'))

        stored = ' '.join(str(value) for value in vars(rows[0]).values())
        self.assertNotIn('12345678Z', stored)
        self.assertNotIn('Ana López', stored)
        self.assertNotIn('120', stored)

    def test_comma_delimiter_and_canonical_headers_without_bom(self):
        text = (
            'plan_code,plan_name,subject_code,subject_name,credits,curricular_year,semester\n'
            'P1,"Plan, uno",S1,Subject,4.5,2,1\n'
        )
        rows, errors = parse_catalogue(text)

        self.assertEqual(errors, [])
        self.assertEqual(rows[0].plan_name, 'Plan, uno')
        self.assertEqual(rows[0].curricular_year, 2)
        self.assertEqual(rows[0].credits, Decimal('4.5'))

    def test_subject_repeated_per_teacher_is_deduplicated(self):
        rows, errors = parse_catalogue(official_csv(
            '2024-25;1234;Plan;500001;Asig;6;111;Teacher A;10;1',
            '2024-25;1234;Plan;500001;Asig;6;222;Teacher B;10;1',
            '2024-25;1234;Plan;500002;Otra;6;111;Teacher A;10;2',
        ))

        self.assertEqual(errors, [])
        self.assertEqual([row.subject_code for row in rows], ['500001', '500002'])

    def test_validation_errors_report_line_numbers(self):
        text = (
            'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'
            ';Plan;S1;Subject;1;1\n'
            'P1;Plan;S2;Subject 2;x;1\n'
            'P1;Plan;S3;Subject 3;7;1\n'
            'P1;Plan;S4;Subject 4;1;4\n'
            'P1;Plan;S5;Subject 5;1;1\n'
            'P1;Plan;S5;Different name;1;1\n'
        )
        rows, errors = parse_catalogue(text)

        self.assertEqual([error.line_number for error in errors], [2, 3, 4, 5, 7])
        self.assertEqual([row.subject_code for row in rows], ['S5'])

    def test_app_sentinel_codes_are_accepted(self):
        rows, errors = parse_catalogue(
            'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'
            'P1;Plan;S1;Elective;10;3\n'
            'P1;Plan;S2;Final project;1000;3\n'
            'P1;Plan;S3;Elective two;10;1\n'
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            [(row.curricular_year, row.semester) for row in rows],
            [(10, 3), (1000, 3), (10, 1)],
        )

    def test_values_outside_code_domain_are_rejected_listing_allowed_values(self):
        rows, errors = parse_catalogue(
            'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'
            'P1;Plan;S1;A;7;1\n'
            'P1;Plan;S2;B;1;4\n'
        )

        self.assertEqual(rows, [])
        self.assertEqual([error.line_number for error in errors], [2, 3])
        self.assertIn('1-6, 10 (optativa) o 1000 (TFE)', str(errors[0]))

    def test_missing_required_header_is_reported(self):
        rows, errors = parse_catalogue('codPlan;Asignatura\nP1;Subject\n')

        self.assertEqual(rows, [])
        self.assertEqual(errors[0].line_number, 1)

    def test_normalize_name_ignores_accents_case_spacing_and_punctuation(self):
        self.assertEqual(
            normalize_name('  Grado en Ingeniería   Civil. '),
            normalize_name('GRADO EN INGENIERIA CIVIL'),
        )


class CatalogueMatchingTests(TestCase):
    def setUp(self):
        self.year = make_year()

    def draft(self, text):
        rows, errors = parse_catalogue(text)
        self.assertEqual(errors, [])
        return build_draft(self.year, rows, 'catalogue.csv', None)

    def test_matches_plan_and_subject_by_code(self):
        plan = Titulacion.objects.create(nombre='Old name', codigo_plan='P1')
        subject = Asignatura.objects.create(nombre='Old subject', codigo_asignatura='S1', titulacion=plan, curso=2, semestre=1)

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;New name;S1;New subject\n')

        row = draft.rows.get()
        self.assertEqual(row.match_status, CatalogueImportRow.MATCH_CODE)
        self.assertEqual(row.target_titulacion, plan)
        self.assertEqual(row.target_asignatura, subject)

    def test_matches_uncoded_plan_by_accent_insensitive_name(self):
        plan = Titulacion.objects.create(nombre='Grado en Ingeniería Informática')

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;GRADO EN INGENIERIA INFORMATICA;S1;Nueva\n')

        row = draft.rows.get()
        self.assertEqual(row.target_titulacion, plan)
        self.assertIsNone(row.target_asignatura)
        self.assertEqual(row.match_status, CatalogueImportRow.MATCH_NEW)

    def test_plan_name_can_be_claimed_by_only_one_plan_code(self):
        plan = Titulacion.objects.create(nombre='Grado en BIM')

        draft = self.draft(
            'codPlan;Plan de estudios;codAsignatura;Asignatura\n'
            'P1;Grado en BIM;S1;A\n'
            'P2;Grado en BIM;S2;B\n'
        )

        self.assertEqual(draft.rows.get(plan_code='P1').target_titulacion, plan)
        second = draft.rows.get(plan_code='P2')
        self.assertIsNone(second.target_titulacion)
        self.assertEqual(second.match_status, CatalogueImportRow.MATCH_NEW)

    def test_ambiguous_plan_name_is_not_matched(self):
        Titulacion.objects.create(nombre='Grado en BIM')
        Titulacion.objects.create(nombre='Grado en BIM')

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;Grado en BIM;S1;A\n')

        self.assertIsNone(draft.rows.get().target_titulacion)

    def test_subject_name_match_is_scoped_to_plan_and_prefills_metadata(self):
        plan = Titulacion.objects.create(nombre='Grado en Química')
        other_plan = Titulacion.objects.create(nombre='Grado en Física')
        Asignatura.objects.create(nombre='Cálculo', titulacion=other_plan, curso=1, semestre=1)
        subject = Asignatura.objects.create(nombre='Cálculo', titulacion=plan, curso=2, semestre=2)

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nPQ;Grado en Quimica;S1;calculo\n')

        row = draft.rows.get()
        self.assertEqual(row.match_status, CatalogueImportRow.MATCH_NAME)
        self.assertEqual(row.target_asignatura, subject)
        self.assertEqual((row.curricular_year, row.semester), (2, 2))

    def test_prefill_copies_elective_and_final_project_codes(self):
        plan = Titulacion.objects.create(nombre='Plan', codigo_plan='P1')
        Asignatura.objects.create(nombre='Optativa', codigo_asignatura='S1', titulacion=plan, curso=10, semestre=3)
        Asignatura.objects.create(nombre='TFG', codigo_asignatura='S2', titulacion=plan, curso=1000, semestre=3)

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;Plan;S1;Optativa\nP1;Plan;S2;TFG\n')

        self.assertEqual(
            {row.subject_code: (row.curricular_year, row.semester) for row in draft.rows.all()},
            {'S1': (10, 3), 'S2': (1000, 3)},
        )

    def test_file_values_win_over_prefill(self):
        plan = Titulacion.objects.create(nombre='Plan', codigo_plan='P1')
        Asignatura.objects.create(nombre='A', codigo_asignatura='S1', titulacion=plan, curso=2, semestre=2)

        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura;Semestre\nP1;Plan;S1;A;1\n')

        row = draft.rows.get()
        self.assertEqual((row.curricular_year, row.semester), (2, 1))


class CatalogueApplyTests(TestCase):
    def setUp(self):
        self.year = make_year()

    def draft(self, text, year=None):
        rows, errors = parse_catalogue(text)
        self.assertEqual(errors, [])
        return build_draft(year or self.year, rows, 'catalogue.csv', None)

    def test_apply_is_blocked_while_rows_are_incomplete(self):
        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;Plan;S1;A\n')

        with self.assertRaises(ValidationError):
            apply_import(draft)

        draft.refresh_from_db()
        self.assertEqual(draft.state, CatalogueImport.STATE_DRAFT)
        self.assertFalse(Titulacion.objects.exists())

    def test_apply_is_blocked_for_archived_year(self):
        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\nP1;Plan;S1;A;1;1\n')
        AcademicYear.objects.filter(pk=self.year.pk).update(state=AcademicYear.STATE_ARCHIVED)

        with self.assertRaises(ValidationError):
            apply_import(draft)

    def test_apply_creates_plan_subject_and_offering(self):
        draft = self.draft(
            'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'
            'P1;Plan uno;S1;Subject one;1;2\n'
            'P1;Plan uno;S2;Subject two;3;1\n'
        )

        apply_import(draft)

        plan = Titulacion.objects.get(codigo_plan='P1')
        self.assertEqual(plan.nombre, 'Plan uno')
        subject = Asignatura.objects.get(titulacion=plan, codigo_asignatura='S1')
        self.assertEqual((subject.curso, subject.semestre), (1, 2))
        offering = SubjectOffering.objects.get(academic_year=self.year, subject=subject)
        self.assertEqual((offering.curricular_year, offering.semester), (1, 2))
        self.assertEqual(self.year.offerings.count(), 2)
        draft.refresh_from_db()
        self.assertEqual(draft.state, CatalogueImport.STATE_APPLIED)
        self.assertIsNotNone(draft.applied_at)
        with self.assertRaises(ValidationError):
            apply_import(draft)

    def test_apply_enriches_existing_uncoded_rows_without_duplicating(self):
        plan = Titulacion.objects.create(nombre='Grado en Ingeniería Civil')
        subject = Asignatura.objects.create(nombre='Hidráulica', titulacion=plan, curso=3, semestre=1)
        teacher = get_user_model().objects.create_user(username='teacher', password='x', role='TEACHER')
        teacher.subjects.add(subject)
        draft = self.draft(
            'codPlan;Plan de estudios;codAsignatura;Asignatura;Semestre\n'
            'PC;Grado en Ingenieria Civil;H1;HIDRAULICA;2\n'
        )

        apply_import(draft)

        self.assertEqual(Titulacion.objects.count(), 1)
        self.assertEqual(Asignatura.objects.count(), 1)
        plan.refresh_from_db()
        subject.refresh_from_db()
        self.assertEqual(plan.codigo_plan, 'PC')
        self.assertEqual(plan.nombre, 'Grado en Ingeniería Civil')
        self.assertEqual(subject.codigo_asignatura, 'H1')
        self.assertEqual(subject.nombre, 'Hidráulica')
        self.assertEqual((subject.curso, subject.semestre), (3, 2))
        self.assertEqual(list(teacher.subjects.all()), [subject])
        self.assertFalse(TeachingAssignment.objects.exists())

    def test_apply_re_resolves_matches_changed_after_draft(self):
        draft = self.draft('codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\nP1;Plan;S1;A;1;1\n')
        plan = Titulacion.objects.create(nombre='Renamed', codigo_plan='P1')

        apply_import(draft)

        self.assertEqual(Titulacion.objects.count(), 1)
        self.assertEqual(draft.rows.get().target_titulacion, plan)
        self.assertTrue(Asignatura.objects.filter(titulacion=plan, codigo_asignatura='S1').exists())

    def test_second_import_for_same_year_is_idempotent(self):
        text = (
            'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'
            'P1;Plan;S1;A;1;1\n'
            'P1;Plan;S2;B;2;2\n'
        )
        apply_import(self.draft(text))
        second = self.draft(text)

        self.assertEqual(set(second.rows.values_list('match_status', flat=True)), {CatalogueImportRow.MATCH_CODE})
        apply_import(second)

        self.assertEqual(Titulacion.objects.count(), 1)
        self.assertEqual(Asignatura.objects.count(), 2)
        self.assertEqual(SubjectOffering.objects.filter(academic_year=self.year).count(), 2)


class CatalogueImportViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', password='x', role='ADMIN')
        self.teacher = User.objects.create_user(username='teacher', password='x', role='TEACHER')

    def test_non_admin_and_anonymous_are_denied(self):
        year = make_year()
        draft = build_draft(year, [], 'empty.csv', None)
        urls = [
            ('get', reverse('catalogue_import_list')),
            ('get', reverse('catalogue_import_detail', args=[draft.pk])),
            ('post', reverse('catalogue_import_apply', args=[draft.pk])),
            ('post', reverse('catalogue_import_delete', args=[draft.pk])),
            ('post', reverse('academic_year_activate', args=[year.pk])),
        ]
        for user in (None, self.teacher):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for method, url in urls:
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302, url)
                self.assertIn(reverse('login'), response['Location'])
        self.assertTrue(CatalogueImport.objects.filter(pk=draft.pk).exists())
        year.refresh_from_db()
        self.assertEqual(year.state, AcademicYear.STATE_DRAFT)

    def test_admin_dashboard_links_to_importer(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertContains(response, reverse('catalogue_import_list'))

    def test_parse_errors_create_nothing(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile('bad.csv', b'codPlan;Plan de estudios;codAsignatura;Asignatura;Semestre\nP1;Plan;S1;A;9\n')

        response = self.client.post(reverse('catalogue_import_list'), {
            'new_year_code': '2026-27',
            'new_year_starts_on': '2026-09-01',
            'new_year_ends_on': '2027-08-31',
            'file': upload,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Línea 2')
        self.assertFalse(AcademicYear.objects.exists())
        self.assertFalse(CatalogueImport.objects.exists())

    def test_admin_upload_preview_save_apply_and_activate(self):
        self.client.force_login(self.admin)
        upload = SimpleUploadedFile('catalogue.csv', official_csv(
            '2024-25;P1;Plan uno;S1;Subject one;6;111;Teacher;10;1',
            '2024-25;P1;Plan uno;S2;Subject two;6;111;Teacher;10;2',
        ))

        response = self.client.post(reverse('catalogue_import_list'), {
            'new_year_code': '2026-27',
            'new_year_starts_on': '2026-09-01',
            'new_year_ends_on': '2027-08-31',
            'file': upload,
        })
        draft = CatalogueImport.objects.get()
        self.assertRedirects(response, reverse('catalogue_import_detail', args=[draft.pk]))
        self.assertEqual(draft.academic_year.code, '2026-27')

        detail_url = reverse('catalogue_import_detail', args=[draft.pk])
        response = self.client.get(detail_url + '?incomplete=1')
        self.assertContains(response, 'Subject one')
        self.assertContains(response, 'disabled title=')

        self.client.post(reverse('catalogue_import_apply', args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.state, CatalogueImport.STATE_DRAFT)

        rows = {row.subject_code: row for row in draft.rows.all()}
        response = self.client.post(detail_url, {
            f'curricular_year_{rows["S1"].pk}': '1',
            f'semester_{rows["S1"].pk}': '1',
            f'curricular_year_{rows["S2"].pk}': '2',
            f'semester_{rows["S2"].pk}': '2',
        })
        self.assertRedirects(response, detail_url)
        self.assertFalse(draft.incomplete_rows().exists())
        self.assertNotContains(self.client.get(detail_url), 'disabled title=')

        response = self.client.post(reverse('catalogue_import_apply', args=[draft.pk]))
        self.assertRedirects(response, detail_url)
        draft.refresh_from_db()
        self.assertEqual(draft.state, CatalogueImport.STATE_APPLIED)
        self.assertEqual(SubjectOffering.objects.filter(academic_year=draft.academic_year).count(), 2)
        self.assertEqual(draft.academic_year.state, AcademicYear.STATE_DRAFT)

        response = self.client.post(reverse('academic_year_activate', args=[draft.academic_year.pk]))
        self.assertRedirects(response, reverse('catalogue_import_list'))
        draft.academic_year.refresh_from_db()
        self.assertEqual(draft.academic_year.state, AcademicYear.STATE_ACTIVE)

    def test_invalid_bulk_values_are_rejected(self):
        self.client.force_login(self.admin)
        year = make_year()
        rows, _ = parse_catalogue('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;Plan;S1;A\n')
        draft = build_draft(year, rows, 'c.csv', self.admin)
        row = draft.rows.get()

        self.client.post(reverse('catalogue_import_detail', args=[draft.pk]), {
            f'curricular_year_{row.pk}': '9',
            f'semester_{row.pk}': '1',
        })

        row.refresh_from_db()
        self.assertIsNone(row.curricular_year)
        self.assertIsNone(row.semester)

    def test_bulk_save_accepts_final_project_and_annual_codes(self):
        self.client.force_login(self.admin)
        year = make_year()
        rows, _ = parse_catalogue('codPlan;Plan de estudios;codAsignatura;Asignatura\nP1;Plan;S1;TFG\n')
        draft = build_draft(year, rows, 'c.csv', self.admin)
        row = draft.rows.get()
        detail_url = reverse('catalogue_import_detail', args=[draft.pk])

        self.client.post(detail_url, {f'curricular_year_{row.pk}': '1000', f'semester_{row.pk}': '3'})

        row.refresh_from_db()
        self.assertEqual((row.curricular_year, row.semester), (1000, 3))
        response = self.client.get(detail_url)
        self.assertContains(response, '<option value="1000" selected>TFE</option>', html=True)
        self.assertContains(response, '<option value="3" selected>Optativa/Anual</option>', html=True)
        apply_import(draft)
        self.assertEqual(SubjectOffering.objects.get(academic_year=year).curricular_year, 1000)

    def test_activation_error_is_reported(self):
        self.client.force_login(self.admin)
        year = make_year()
        plan = Titulacion.objects.create(nombre='Plan', codigo_plan='P1')
        subject = Asignatura.objects.create(nombre='A', codigo_asignatura='S1', titulacion=plan, curso=1, semestre=1)
        SubjectOffering.objects.create(academic_year=year, subject=subject)

        response = self.client.post(reverse('academic_year_activate', args=[year.pk]), follow=True)

        self.assertContains(response, 'No se puede activar el curso 2026-27')
        year.refresh_from_db()
        self.assertEqual(year.state, AcademicYear.STATE_DRAFT)
