from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from .catalogue_import import (
    apply_import,
    build_draft,
    find_subject_conflicts,
    normalize_name,
    parse_catalogue,
    OVERRIDE_AUTO,
    OVERRIDE_NEW,
    OVERRIDE_TITULACION,
    register_plan_code,
    set_plan_override,
)
from .models import (
    AcademicYear,
    Asignatura,
    CatalogueImport,
    CatalogueImportPlanOverride,
    CatalogueImportRow,
    PlanCodeAlias,
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

    def test_activation_archives_previously_active_year(self):
        previous = AcademicYear.objects.create(
            code='2025-26',
            starts_on=date(2025, 9, 1),
            ends_on=date(2026, 8, 31),
            state=AcademicYear.STATE_ACTIVE,
        )
        SubjectOffering.objects.create(
            academic_year=self.year, subject=self.subject, curricular_year=1, semester=1
        )

        self.year.activate()

        previous.refresh_from_db()
        self.year.refresh_from_db()
        self.assertEqual(previous.state, AcademicYear.STATE_ARCHIVED)
        self.assertEqual(self.year.state, AcademicYear.STATE_ACTIVE)

    def test_failed_activation_keeps_previously_active_year(self):
        previous = AcademicYear.objects.create(
            code='2025-26',
            starts_on=date(2025, 9, 1),
            ends_on=date(2026, 8, 31),
            state=AcademicYear.STATE_ACTIVE,
        )
        SubjectOffering.objects.create(academic_year=self.year, subject=self.subject)

        with self.assertRaises(ValidationError):
            self.year.activate()

        previous.refresh_from_db()
        self.assertEqual(previous.state, AcademicYear.STATE_ACTIVE)

    def test_year_without_offerings_cannot_activate(self):
        with self.assertRaises(ValidationError):
            self.year.activate()

    def test_archived_year_cannot_be_reactivated(self):
        SubjectOffering.objects.create(
            academic_year=self.year, subject=self.subject, curricular_year=1, semester=1
        )
        self.year.state = AcademicYear.STATE_ARCHIVED
        self.year.save(update_fields=['state'])

        with self.assertRaises(ValidationError):
            self.year.activate()


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

    def test_second_code_sharing_a_plan_name_is_grouped_as_alias(self):
        plan = Titulacion.objects.create(nombre='Grado en BIM')

        draft = self.draft(
            'codPlan;Plan de estudios;codAsignatura;Asignatura\n'
            'P2;Grado en BIM;S2;B\n'
            'P1;Grado en BIM;S1;A\n'
        )

        first = draft.rows.get(plan_code='P1')
        second = draft.rows.get(plan_code='P2')
        self.assertEqual((first.target_titulacion, first.plan_role), (plan, CatalogueImportRow.ROLE_PRIMARY))
        self.assertEqual((second.target_titulacion, second.plan_role), (plan, CatalogueImportRow.ROLE_ALIAS))
        self.assertEqual(first.plan_group, second.plan_group)

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


CIVIL = 'GRADO EN INGENIERÍA CIVIL'
BIM = 'MÁSTER U. METODOLOGÍA PARA MODELIZACIÓN INFORMACIÓN CONSTRUCCIÓN (BIM)'
GROUPING_HEADER = 'codPlan;Plan de estudios;codAsignatura;Asignatura;curso_plan;Semestre\n'


class CataloguePlanGroupingTests(TestCase):
    def setUp(self):
        self.year = make_year()

    def draft(self, body, year=None):
        rows, errors = parse_catalogue(GROUPING_HEADER + body)
        self.assertEqual(errors, [])
        return build_draft(year or self.year, rows, 'catalogue.csv', None)

    def roles(self, draft):
        return {
            row.plan_code: (row.plan_role, row.target_titulacion_id, row.plan_group)
            for row in draft.rows.all()
        }

    def civil_body(self, mentions_first):
        base = f'1640;{CIVIL};500900;MATEMÁTICAS I;1;1\n'
        mentions = (
            f'1623;{CIVIL} - CONSTRUCCIONES CIVILES;500922;HIDRÁULICA E HIDROLOGÍA;2;1\n'
            f'1624;{CIVIL} - HIDROLOGÍA;500922;HIDRÁULICA E HIDROLOGÍA;2;1\n'
            f'1625;{CIVIL} - TRANSPORTES Y SERVICIOS URBANOS;500950;TRANSPORTES;3;2\n'
        )
        return mentions + base if mentions_first else base + mentions

    def assert_civil_grouped(self, civil):
        self.assertEqual(Titulacion.objects.count(), 1)
        civil.refresh_from_db()
        self.assertEqual(civil.codigo_plan, '1640')
        self.assertEqual(
            sorted(civil.plan_code_aliases.values_list('code', 'name')),
            [
                ('1623', f'{CIVIL} - CONSTRUCCIONES CIVILES'),
                ('1624', f'{CIVIL} - HIDROLOGÍA'),
                ('1625', f'{CIVIL} - TRANSPORTES Y SERVICIOS URBANOS'),
            ],
        )
        self.assertEqual(Asignatura.objects.filter(titulacion=civil, codigo_asignatura='500922').count(), 1)
        self.assertEqual(SubjectOffering.objects.filter(academic_year=self.year).count(), 3)

    def test_civil_mentions_group_into_existing_titulacion(self):
        for mentions_first in (False, True):
            with self.subTest(mentions_first=mentions_first):
                with transaction.atomic():
                    civil = Titulacion.objects.create(nombre='Grado En Ingeniería Civil')
                    draft = self.draft(self.civil_body(mentions_first))

                    roles = self.roles(draft)
                    self.assertEqual(roles['1640'][:2], (CatalogueImportRow.ROLE_PRIMARY, civil.pk))
                    for code in ('1623', '1624', '1625'):
                        self.assertEqual(roles[code][:2], (CatalogueImportRow.ROLE_ALIAS, civil.pk))
                    self.assertEqual(len({role[2] for role in roles.values()}), 1)

                    apply_import(draft)
                    self.assert_civil_grouped(civil)
                    transaction.set_rollback(True)

    def test_two_bim_codes_with_same_name_group_into_one_new_titulacion(self):
        draft = self.draft(
            f'1645;{BIM};600002;GESTIÓN BIM;1;2\n'
            f'1642;{BIM};600001;MODELADO BIM;1;1\n'
        )

        roles = self.roles(draft)
        self.assertEqual(roles['1642'][0], CatalogueImportRow.ROLE_PRIMARY)
        self.assertEqual(roles['1645'][0], CatalogueImportRow.ROLE_ALIAS)
        self.assertEqual(roles['1642'][2], roles['1645'][2])

        apply_import(draft)

        bim = Titulacion.objects.get()
        self.assertEqual(bim.codigo_plan, '1642')
        self.assertEqual(list(bim.plan_code_aliases.values_list('code', flat=True)), ['1645'])
        self.assertEqual(bim.asignatura_set.count(), 2)

    def test_brand_new_degree_groups_its_mentions_within_the_file(self):
        draft = self.draft(
            'P9 - X;GRADO NUEVO - MENCIÓN A;S2;B;2;1\n'
            'P1;GRADO NUEVO;S1;A;1;1\n'
        )

        roles = self.roles(draft)
        self.assertEqual(roles['P1'][0], CatalogueImportRow.ROLE_PRIMARY)
        self.assertEqual(roles['P9 - X'][0], CatalogueImportRow.ROLE_ALIAS)
        self.assertEqual(roles['P1'][2], roles['P9 - X'][2])

        apply_import(draft)

        degree = Titulacion.objects.get()
        self.assertEqual((degree.nombre, degree.codigo_plan), ('GRADO NUEVO', 'P1'))
        self.assertEqual(degree.plan_code_aliases.get().code, 'P9 - X')

    def test_second_import_resolves_alias_codes_without_new_titulacion(self):
        civil = Titulacion.objects.create(nombre='Grado En Ingeniería Civil')
        apply_import(self.draft(self.civil_body(mentions_first=False)))

        next_year = make_year('2027-28')
        second = self.draft(self.civil_body(mentions_first=True), year=next_year)

        self.assertEqual({row.plan_match_status for row in second.rows.all()}, {CatalogueImportRow.MATCH_CODE})
        self.assertEqual({row.match_status for row in second.rows.all()}, {CatalogueImportRow.MATCH_CODE})
        apply_import(second)

        self.assertEqual(Titulacion.objects.count(), 1)
        self.assertEqual(PlanCodeAlias.objects.filter(titulacion=civil).count(), 3)
        self.assertEqual(Asignatura.objects.count(), 3)
        self.assertEqual(SubjectOffering.objects.filter(academic_year=next_year).count(), 3)

    def test_conflicting_grouped_duplicate_subject_blocks_apply(self):
        Titulacion.objects.create(nombre=CIVIL)
        draft = self.draft(
            f'1640;{CIVIL};500900;MATEMÁTICAS I;1;1\n'
            f'1623;{CIVIL} - CONSTRUCCIONES CIVILES;500922;HIDRÁULICA;2;1\n'
            f'1624;{CIVIL} - HIDROLOGÍA;500922;HIDRÁULICA;3;1\n'
        )

        conflicts = find_subject_conflicts(draft.rows.all())
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((conflicts[0].subject_code, conflicts[0].fields), ('500922', ['curso']))
        with self.assertRaises(ValidationError):
            apply_import(draft)
        self.assertFalse(Asignatura.objects.exists())

        draft.rows.filter(plan_code='1624').update(curricular_year=2)
        apply_import(draft)
        self.assertEqual(Asignatura.objects.filter(codigo_asignatura='500922').count(), 1)

    def test_grouped_duplicates_share_known_curricular_metadata(self):
        Titulacion.objects.create(nombre=CIVIL)
        draft = self.draft(
            f'1623;{CIVIL} - CONSTRUCCIONES CIVILES;500932;GEOTECNIA;;\n'
            f'1624;{CIVIL} - HIDROLOGÍA;500932;GEOTECNIA;2;2\n'
        )

        self.assertEqual(set(draft.rows.values_list('curricular_year', 'semester')), {(2, 2)})

    def test_alias_belonging_to_another_titulacion_raises(self):
        civil = Titulacion.objects.create(nombre=CIVIL, codigo_plan='1640')
        other = Titulacion.objects.create(nombre='Other degree', codigo_plan='9999')
        PlanCodeAlias.objects.create(code='1623', titulacion=other, name='Other mention')

        with self.assertRaises(ValidationError):
            register_plan_code(civil, '1623', f'{CIVIL} - CONSTRUCCIONES CIVILES', CatalogueImportRow.ROLE_ALIAS)
        with self.assertRaises(ValidationError):
            register_plan_code(civil, '9999', 'Other degree', CatalogueImportRow.ROLE_ALIAS)
        with self.assertRaises(ValidationError):
            register_plan_code(civil, '1641', CIVIL, CatalogueImportRow.ROLE_PRIMARY)
        self.assertEqual(PlanCodeAlias.objects.get(code='1623').titulacion, other)

    def test_preview_shows_mention_badge_and_conflicts(self):
        admin = get_user_model().objects.create_user(username='admin', password='x', role='ADMIN')
        self.client.force_login(admin)
        Titulacion.objects.create(nombre=CIVIL)
        draft = self.draft(
            f'1640;{CIVIL};500900;MATEMÁTICAS I;1;1\n'
            f'1623;{CIVIL} - CONSTRUCCIONES CIVILES;500922;HIDRÁULICA;2;1\n'
            f'1624;{CIVIL} - HIDROLOGÍA;500922;HIDRÁULICA;3;1\n'
        )

        response = self.client.get(reverse('catalogue_import_detail', args=[draft.pk]))

        self.assertContains(response, f'Mención de {CIVIL}')
        self.assertContains(response, 'aparece en los planes 1623, 1624')
        self.assertFalse(response.context['can_apply'])
        self.assertEqual(response.context['summary']['grouped_codes'], 2)


LEGACY_BIM = (
    'Máster Universitario En Metodología Para La Modelización De La Información De La Construcción '
    '(building Information Modeling Bim) En El Desarrollo Colaborativo De Proyectos'
)


class CataloguePlanOverrideTests(TestCase):
    def setUp(self):
        self.year = make_year()
        self.legacy = Titulacion.objects.create(nombre=LEGACY_BIM)
        self.modelling = Asignatura.objects.create(nombre='Modelado BIM', titulacion=self.legacy, curso=1, semestre=2)
        self.management = Asignatura.objects.create(nombre='Gestión BIM', titulacion=self.legacy, curso=1, semestre=1)
        rows, errors = parse_catalogue(
            GROUPING_HEADER
            + f'1642;{BIM};600001;MODELADO BIM;;\n'
            + f'1645;{BIM};600002;GESTION BIM;;\n'
        )
        self.assertEqual(errors, [])
        self.draft = build_draft(self.year, rows, 'catalogue.csv', None)

    def row(self, plan_code):
        return self.draft.rows.select_related('target_titulacion', 'target_asignatura').get(plan_code=plan_code)

    def test_abbreviated_name_is_new_without_override(self):
        self.assertIsNone(self.row('1642').target_titulacion)
        self.assertEqual(self.row('1645').plan_role, CatalogueImportRow.ROLE_ALIAS)

    def test_override_maps_to_legacy_titulacion_and_sibling_joins(self):
        set_plan_override(self.draft, '1642', OVERRIDE_TITULACION, self.legacy)

        primary, sibling = self.row('1642'), self.row('1645')
        self.assertEqual(
            (primary.target_titulacion, primary.plan_role, primary.plan_match_status),
            (self.legacy, CatalogueImportRow.ROLE_PRIMARY, CatalogueImportRow.MATCH_MANUAL),
        )
        self.assertEqual((sibling.target_titulacion, sibling.plan_role), (self.legacy, CatalogueImportRow.ROLE_ALIAS))
        self.assertEqual(primary.plan_group, sibling.plan_group)
        self.assertEqual(primary.target_asignatura, self.modelling)
        self.assertEqual(sibling.target_asignatura, self.management)
        self.assertEqual((primary.curricular_year, primary.semester), (1, 2))
        self.assertEqual((sibling.curricular_year, sibling.semester), (1, 1))
        self.assertEqual(primary.match_status, CatalogueImportRow.MATCH_MANUAL)

    def test_apply_with_override_creates_no_duplicate_titulacion(self):
        set_plan_override(self.draft, '1642', OVERRIDE_TITULACION, self.legacy)

        apply_import(self.draft)

        self.assertEqual(Titulacion.objects.count(), 1)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.nombre, LEGACY_BIM)
        self.assertEqual(self.legacy.codigo_plan, '1642')
        self.assertEqual(list(self.legacy.plan_code_aliases.values_list('code', flat=True)), ['1645'])
        self.assertEqual(Asignatura.objects.count(), 2)
        self.modelling.refresh_from_db()
        self.assertEqual(self.modelling.codigo_asignatura, '600001')

    def test_mentions_follow_overridden_parent(self):
        legacy_civil = Titulacion.objects.create(nombre='Grado en Ingeniería Civil (plan antiguo)')
        rows, _ = parse_catalogue(
            GROUPING_HEADER
            + 'P2;GRADO CIVIL ABREV - HIDROLOGÍA;S2;B;2;1\n'
            + 'P1;GRADO CIVIL ABREV;S1;A;1;1\n'
        )
        draft = build_draft(self.year, rows, 'civil.csv', None)

        set_plan_override(draft, 'P1', OVERRIDE_TITULACION, legacy_civil)

        mention = draft.rows.get(plan_code='P2')
        self.assertEqual((mention.target_titulacion, mention.plan_role), (legacy_civil, CatalogueImportRow.ROLE_ALIAS))

    def test_create_new_forces_new_even_when_name_matches(self):
        civil = Titulacion.objects.create(nombre=CIVIL)
        rows, _ = parse_catalogue(GROUPING_HEADER + f'1640;{CIVIL};500900;MATEMÁTICAS I;1;1\n')
        draft = build_draft(self.year, rows, 'civil.csv', None)
        self.assertEqual(draft.rows.get().target_titulacion, civil)

        set_plan_override(draft, '1640', OVERRIDE_NEW)

        row = draft.rows.get()
        self.assertIsNone(row.target_titulacion)
        self.assertEqual(row.plan_match_status, CatalogueImportRow.MATCH_MANUAL)
        apply_import(draft)
        self.assertEqual(Titulacion.objects.filter(nombre=CIVIL).count(), 2)
        civil.refresh_from_db()
        self.assertIsNone(civil.codigo_plan)

    def test_removing_override_restores_automatic_mapping(self):
        set_plan_override(self.draft, '1642', OVERRIDE_TITULACION, self.legacy)
        set_plan_override(self.draft, '1642', OVERRIDE_AUTO)

        self.assertFalse(CatalogueImportPlanOverride.objects.exists())
        row = self.row('1642')
        self.assertIsNone(row.target_titulacion)
        self.assertEqual(row.plan_match_status, CatalogueImportRow.MATCH_NEW)

    def test_code_matched_plan_cannot_be_overridden(self):
        coded = Titulacion.objects.create(nombre='Coded', codigo_plan='1700')
        rows, _ = parse_catalogue(GROUPING_HEADER + '1700;Coded;S1;A;1;1\n')
        draft = build_draft(self.year, rows, 'coded.csv', None)

        with self.assertRaises(ValidationError):
            set_plan_override(draft, '1700', OVERRIDE_TITULACION, self.legacy)

        self.assertFalse(CatalogueImportPlanOverride.objects.exists())
        self.assertEqual(draft.rows.get().target_titulacion, coded)

    def test_override_onto_titulacion_with_other_code_is_alias(self):
        self.legacy.codigo_plan = '1500'
        self.legacy.save()

        set_plan_override(self.draft, '1642', OVERRIDE_TITULACION, self.legacy)

        self.assertEqual(self.row('1642').plan_role, CatalogueImportRow.ROLE_ALIAS)
        apply_import(self.draft)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.codigo_plan, '1500')
        self.assertEqual(sorted(self.legacy.plan_code_aliases.values_list('code', flat=True)), ['1642', '1645'])

    def test_admin_edited_values_survive_override(self):
        self.draft.rows.filter(plan_code='1642').update(curricular_year=10, semester=3)

        set_plan_override(self.draft, '1642', OVERRIDE_TITULACION, self.legacy)

        row = self.row('1642')
        self.assertEqual(row.target_asignatura, self.modelling)
        self.assertEqual((row.curricular_year, row.semester), (10, 3))

    def test_override_endpoint_admin_flow_and_non_admin_denied(self):
        url = reverse('catalogue_import_plan_override', args=[self.draft.pk])
        User = get_user_model()
        teacher = User.objects.create_user(username='teacher', password='x', role='TEACHER')
        self.client.force_login(teacher)
        response = self.client.post(url, {'plan_code': '1642', 'target': str(self.legacy.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])
        self.assertFalse(CatalogueImportPlanOverride.objects.exists())

        admin = User.objects.create_user(username='admin', password='x', role='ADMIN')
        self.client.force_login(admin)
        detail_url = reverse('catalogue_import_detail', args=[self.draft.pk])
        self.assertContains(self.client.get(detail_url), 'Automático (nueva titulación)')

        response = self.client.post(url, {'plan_code': '1642', 'target': str(self.legacy.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CatalogueImportPlanOverride.objects.get().titulacion, self.legacy)
        response = self.client.get(detail_url)
        self.assertContains(response, 'Asociación manual')
        self.assertEqual(response.context['summary']['manual_plans'], 1)

        apply_import(self.draft)
        response = self.client.post(url, {'plan_code': '1642', 'target': 'new'}, follow=True)
        self.assertContains(response, 'Solo se pueden modificar importaciones en borrador.')
        response = self.client.get(detail_url)
        self.assertNotContains(response, 'name="target"')
        self.assertContains(response, 'Asociación manual')


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
