"""Tests for importing activities from a Moodle calendar export (.ics).

The fixture ``test_data/moodle_calendar.ics`` is synthetic but mirrors the real
export: folded lines with TAB continuations, escaped commas and newlines, 45
repeats of one summary, two zero-duration milestones, two one-off seminars and a
date range that crosses the CEST -> CET change.
"""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AcademicYear, Asignatura, SubjectOffering, Titulacion
from users.models import CustomUser

from . import ical_import
from .ical_import import (
    IcalImportRefused,
    apply_import,
    build_draft,
    group_events,
    parse_calendar,
)
from .models import Actividad, IcalImport, IcalImportEvent, LogActividad, MoodleCourseSubject, TipoActividad

FIXTURE = Path(__file__).resolve().parent / 'test_data' / 'moodle_calendar.ics'
PASSWORD = 'ical-import-password-1'

CALENDAR_HEADER = (
    'BEGIN:VCALENDAR\r\n'
    'METHOD:PUBLISH\r\n'
    'PRODID:-//Moodle Pty Ltd//NONSGML Moodle Version 2026042002.02//EN\r\n'
    'VERSION:2.0\r\n'
)


def calendar_with(*events):
    return CALENDAR_HEADER + ''.join(events) + 'END:VCALENDAR\r\n'


def vevent(uid, summary='Evento', extra=''):
    return (
        'BEGIN:VEVENT\r\n'
        f'UID:{uid}@campusvirtual.example.org/aula\r\n'
        f'SUMMARY:{summary}\r\n'
        'CLASS:PUBLIC\r\n'
        'DTSTAMP:20260917T080428Z\r\n'
        f'{extra}'
        'CATEGORIES:99001\r\n'
        'END:VEVENT\r\n'
    )


def fixture_bytes():
    return FIXTURE.read_bytes()


class ParserTests(TestCase):
    def test_parses_the_whole_fixture(self):
        parsed = parse_calendar(fixture_bytes())
        self.assertEqual(len(parsed.events), 49)
        self.assertEqual(parsed.moodle_course_id, '99001')
        summaries = {}
        for event in parsed.events:
            summaries[event.summary] = summaries.get(event.summary, 0) + 1
        self.assertEqual(summaries['Asistencia clases'], 45)
        self.assertEqual(summaries['1º Seminario evaluable'], 1)

    def test_folded_lines_and_escapes_are_decoded(self):
        parsed = parse_calendar(fixture_bytes())
        milestone = next(e for e in parsed.events if e.summary.startswith('Se abre'))
        self.assertIn('carácter global, de manera', milestone.description)
        self.assertNotIn('\\,', milestone.description)
        self.assertNotIn('\\n', milestone.description)
        self.assertIn('\n\nRELLENA', milestone.description)
        # A folded description is rejoined without the TAB continuation markers.
        self.assertNotIn('\t', milestone.description)

    def test_missing_description_becomes_empty_text(self):
        parsed = parse_calendar(fixture_bytes())
        lesson = next(e for e in parsed.events if e.summary == 'Asistencia clases')
        self.assertEqual(lesson.description, '')

    def test_utc_is_converted_to_the_project_timezone_across_the_dst_change(self):
        parsed = parse_calendar(fixture_bytes())
        by_uid = {event.uid.split('@')[0]: event for event in parsed.events}
        september = timezone.localtime(by_uid['700001'].starts_at)
        self.assertEqual((september.month, september.hour, september.minute), (9, 17, 30))
        december = next(e for e in parsed.events if e.summary == '2º seminario evaluable')
        december_local = timezone.localtime(december.starts_at)
        self.assertEqual((december_local.month, december_local.hour, december_local.minute), (12, 16, 30))

    def test_zero_duration_events_keep_start_equal_to_end(self):
        parsed = parse_calendar(fixture_bytes())
        milestones = [event for event in parsed.events if event.zero_duration]
        self.assertEqual(len(milestones), 2)
        for event in milestones:
            self.assertEqual(event.starts_at, event.ends_at)

    def test_date_only_events_are_all_day(self):
        calendar = calendar_with(vevent(
            1, 'Entrega', 'DTSTART;VALUE=DATE:20261102\r\nDTEND;VALUE=DATE:20261104\r\n'
        ))
        event = parse_calendar(calendar).events[0]
        self.assertTrue(event.all_day)
        self.assertFalse(event.zero_duration)
        start = timezone.localtime(event.starts_at)
        end = timezone.localtime(event.ends_at)
        self.assertEqual((start.date(), start.hour, start.minute), (date(2026, 11, 2), 0, 0))
        self.assertEqual((end.date(), end.hour, end.minute), (date(2026, 11, 3), 23, 59))

    def test_single_date_only_event_ends_the_same_day(self):
        calendar = calendar_with(vevent(1, 'Entrega', 'DTSTART;VALUE=DATE:20261102\r\n'))
        event = parse_calendar(calendar).events[0]
        end = timezone.localtime(event.ends_at)
        self.assertEqual((end.date(), end.hour, end.minute), (date(2026, 11, 2), 23, 59))

    def test_recurring_events_are_flagged_and_never_expanded(self):
        calendar = calendar_with(vevent(
            1, 'Tutoría',
            'DTSTART:20260914T153000Z\r\nDTEND:20260914T163000Z\r\nRRULE:FREQ=WEEKLY;COUNT=10\r\n',
        ))
        parsed = parse_calendar(calendar)
        self.assertEqual(len(parsed.events), 1)
        self.assertEqual(parsed.events[0].unsupported_reason, ical_import.UNSUPPORTED_RECURRENCE)

    def test_vtodo_and_vjournal_are_ignored(self):
        calendar = calendar_with(
            vevent(1, 'Clase', 'DTSTART:20260914T153000Z\r\nDTEND:20260914T163000Z\r\n'),
            'BEGIN:VTODO\r\nUID:t1\r\nSUMMARY:Tarea\r\nDUE:20260914T153000Z\r\nEND:VTODO\r\n',
            'BEGIN:VJOURNAL\r\nUID:j1\r\nSUMMARY:Nota\r\nDTSTART:20260914T153000Z\r\nEND:VJOURNAL\r\n',
        )
        parsed = parse_calendar(calendar)
        self.assertEqual([event.summary for event in parsed.events], ['Clase'])

    def test_calendar_without_events_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            parse_calendar(calendar_with())
        self.assertIn('ningún evento', caught.exception.messages[0])

    def test_non_icalendar_content_is_rejected(self):
        for payload in (b'esto no es un calendario', b'nombre;codigo\nA;1\n', b'%PDF-1.4\n%\xc3\xa9'):
            with self.subTest(payload=payload[:12]):
                with self.assertRaises(ValidationError):
                    parse_calendar(payload)

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ValidationError):
            parse_calendar(b'   ')

    def test_repeated_uids_are_kept_once(self):
        event = vevent(1, 'Clase', 'DTSTART:20260914T153000Z\r\nDTEND:20260914T163000Z\r\n')
        parsed = parse_calendar(calendar_with(event, event))
        self.assertEqual(len(parsed.events), 1)


class FixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(
            code='2026-27', starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31),
            state=AcademicYear.STATE_ACTIVE,
        )
        cls.plan = Titulacion.objects.create(nombre='Grado en Ingeniería', codigo_plan='P1')
        cls.subject = Asignatura.objects.create(
            nombre='Cálculo', codigo_asignatura='S1', titulacion=cls.plan, curso=1, semestre=1,
        )
        cls.other_subject = Asignatura.objects.create(
            nombre='Física', codigo_asignatura='S2', titulacion=cls.plan, curso=1, semestre=1,
        )
        SubjectOffering.objects.create(academic_year=cls.year, subject=cls.subject, curricular_year=1, semester=1)
        cls.teacher = CustomUser.objects.create_user(
            username='ical_teacher', email='ical_teacher@unex.es', password=PASSWORD,
            role=CustomUser.ROLE_TEACHER,
        )
        cls.teacher.subjects.set([cls.subject])
        cls.student = CustomUser.objects.create_user(
            username='ical_student', email='ical_student@alumnos.unex.es', password=PASSWORD,
            role=CustomUser.ROLE_STUDENT,
        )
        cls.tipo = TipoActividad.objects.create(nombre='Clase')
        cls.tipo_examen = TipoActividad.objects.create(nombre='Examen')

    def make_draft(self, subject=None, user=None):
        parsed = parse_calendar(fixture_bytes())
        return build_draft(
            parsed, subject or self.subject, self.year, 'icalexport.ics', user or self.teacher
        )


class GroupingTests(FixtureMixin, TestCase):
    def test_groups_share_a_normalized_summary(self):
        draft = self.make_draft()
        groups = group_events(list(draft.events.all()))
        self.assertEqual([group.count for group in groups][0], 45)
        self.assertEqual({group.summary for group in groups}, {
            'Asistencia clases', 'Se abre Elección del sistema de evaluación',
            'Se cierra Elección del sistema de evaluación',
            '1º Seminario evaluable', '2º seminario evaluable',
        })

    def test_case_and_whitespace_do_not_split_a_group(self):
        calendar = calendar_with(
            vevent(1, 'Seminario  Evaluable', 'DTSTART:20260914T153000Z\r\nDTEND:20260914T163000Z\r\n'),
            vevent(2, 'seminario evaluable', 'DTSTART:20260921T153000Z\r\nDTEND:20260921T163000Z\r\n'),
        )
        draft = build_draft(parse_calendar(calendar), self.subject, self.year, 'c.ics', self.teacher)
        groups = group_events(list(draft.events.all()))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 2)

    def test_groups_are_ordered_by_their_first_date(self):
        draft = self.make_draft()
        groups = group_events(list(draft.events.all()))
        self.assertEqual([group.first_date for group in groups], sorted(group.first_date for group in groups))

    def test_large_groups_start_unselected_and_small_ones_selected(self):
        draft = self.make_draft()
        by_summary = {group.summary: group for group in group_events(list(draft.events.all()))}
        self.assertEqual(by_summary['Asistencia clases'].selected_count, 0)
        for summary in ('1º Seminario evaluable', '2º seminario evaluable',
                        'Se abre Elección del sistema de evaluación'):
            self.assertEqual(by_summary[summary].selected_count, 1, summary)

    def test_already_imported_events_are_marked_and_unselected(self):
        first = self.make_draft()
        self.select_and_apply(first, ['1º Seminario evaluable'])
        second = self.make_draft()
        duplicate = second.events.get(summary='1º Seminario evaluable')
        self.assertEqual(duplicate.status, IcalImportEvent.STATUS_DUPLICATE)
        self.assertFalse(duplicate.selected)
        self.assertFalse(duplicate.is_importable)

    def select_and_apply(self, draft, summaries):
        draft.events.update(selected=False)
        draft.events.filter(summary__in=summaries).update(selected=True, tipo_actividad=self.tipo)
        return apply_import(draft, self.teacher)


class ApplyTests(FixtureMixin, TestCase):
    def select(self, draft, summaries, tipo=None, evaluable=False, porcentaje='0.00'):
        draft.events.update(selected=False)
        draft.events.filter(summary__in=summaries).update(
            selected=True, tipo_actividad=tipo or self.tipo,
            evaluable=evaluable, porcentaje_evaluacion=Decimal(porcentaje),
        )

    def test_creates_one_activity_per_selected_event(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable', '2º seminario evaluable'], tipo=self.tipo_examen,
                    evaluable=True, porcentaje='25.00')
        result = apply_import(draft, self.teacher)

        self.assertEqual((result.created, result.skipped, result.failed), (2, 0, 0))
        activity = Actividad.objects.get(nombre='1º Seminario evaluable')
        self.assertEqual(activity.academic_year, self.year)
        self.assertEqual(list(activity.asignaturas.all()), [self.subject])
        self.assertEqual(activity.tipo_actividad, self.tipo_examen)
        self.assertTrue(activity.evaluable)
        self.assertEqual(activity.porcentaje_evaluacion, Decimal('25.00'))
        self.assertEqual(activity.descripcion, 'Entrega en el aula virtual, antes de las 23:59')
        self.assertTrue(activity.ical_uid.endswith('@campusvirtual.example.org/aula'))
        # Evaluable with >= 10% follows the normal rule: it needs approval.
        self.assertFalse(activity.aprobada)
        self.assertTrue(LogActividad.objects.filter(actividad=activity, tipo_log='Creation').exists())

        draft.refresh_from_db()
        self.assertEqual(draft.state, IcalImport.STATE_APPLIED)
        self.assertIsNotNone(draft.applied_at)

    def test_non_evaluable_activities_follow_the_normal_approval_rule(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        apply_import(draft, self.teacher)
        self.assertTrue(Actividad.objects.get(nombre='1º Seminario evaluable').aprobada)

    def test_activity_keeps_the_local_start_and_end(self):
        draft = self.make_draft()
        self.select(draft, ['2º seminario evaluable'])
        apply_import(draft, self.teacher)
        activity = Actividad.objects.get(nombre='2º seminario evaluable')
        local = timezone.localtime(activity.fecha_inicio)
        self.assertEqual((local.year, local.month, local.day, local.hour, local.minute), (2026, 12, 22, 16, 30))

    def test_zero_duration_events_keep_their_instant(self):
        draft = self.make_draft()
        self.select(draft, ['Se abre Elección del sistema de evaluación'])
        apply_import(draft, self.teacher)
        activity = Actividad.objects.get(nombre='Se abre Elección del sistema de evaluación')
        self.assertEqual(activity.fecha_inicio, activity.fecha_fin)

    def test_applying_twice_skips_the_duplicates(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        apply_import(draft, self.teacher)
        result = apply_import(draft, self.teacher)
        self.assertEqual((result.created, result.skipped), (0, 1))
        self.assertEqual(Actividad.objects.filter(nombre='1º Seminario evaluable').count(), 1)

    def test_a_second_import_of_the_same_file_creates_nothing_new(self):
        first = self.make_draft()
        self.select(first, ['1º Seminario evaluable'])
        apply_import(first, self.teacher)
        second = self.make_draft()
        self.select(second, ['1º Seminario evaluable'])
        result = apply_import(second, self.teacher)
        self.assertEqual(result.created, 0)
        self.assertEqual(Actividad.objects.filter(ical_uid__isnull=False).count(), 1)

    def test_events_without_activity_type_are_refused(self):
        draft = self.make_draft()
        draft.events.update(selected=False)
        draft.events.filter(summary='1º Seminario evaluable').update(selected=True, tipo_actividad=None)
        with self.assertRaises(IcalImportRefused) as caught:
            apply_import(draft, self.teacher)
        self.assertIn('tipo de actividad', caught.exception.messages[0])
        self.assertEqual(Actividad.objects.count(), 0)

    def test_empty_selection_is_refused(self):
        draft = self.make_draft()
        draft.events.update(selected=False)
        with self.assertRaises(IcalImportRefused):
            apply_import(draft, self.teacher)

    def test_subject_no_longer_offered_is_refused(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        SubjectOffering.objects.filter(academic_year=self.year, subject=self.subject).update(
            state=SubjectOffering.STATE_WITHDRAWN
        )
        with self.assertRaises(IcalImportRefused) as caught:
            apply_import(draft, self.teacher)
        self.assertIn('no se oferta', caught.exception.messages[0])

    def test_teacher_who_no_longer_teaches_the_subject_is_refused(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        self.teacher.subjects.clear()
        with self.assertRaises(IcalImportRefused) as caught:
            apply_import(draft, self.teacher)
        self.assertIn('Ya no impartes', caught.exception.messages[0])

    def test_inactive_year_is_refused(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        AcademicYear.objects.filter(pk=self.year.pk).update(state=AcademicYear.STATE_ARCHIVED)
        with self.assertRaises(IcalImportRefused) as caught:
            apply_import(draft, self.teacher)
        self.assertIn('curso académico activo', caught.exception.messages[0])

    def test_draft_cannot_be_built_for_a_subject_not_offered(self):
        parsed = parse_calendar(fixture_bytes())
        with self.assertRaises(IcalImportRefused):
            build_draft(parsed, self.other_subject, self.year, 'c.ics', self.teacher)

    def test_recurring_events_are_never_imported(self):
        calendar = calendar_with(vevent(
            1, 'Tutoría',
            'DTSTART:20260914T153000Z\r\nDTEND:20260914T163000Z\r\nRRULE:FREQ=WEEKLY;COUNT=10\r\n',
        ))
        draft = build_draft(parse_calendar(calendar), self.subject, self.year, 'c.ics', self.teacher)
        event = draft.events.get()
        self.assertEqual(event.status, IcalImportEvent.STATUS_UNSUPPORTED)
        self.assertFalse(event.selected)
        with self.assertRaises(IcalImportRefused):
            apply_import(draft, self.teacher)

    def test_mapping_is_remembered_when_the_import_is_applied(self):
        draft = self.make_draft()
        self.select(draft, ['1º Seminario evaluable'])
        apply_import(draft, self.teacher)
        mapping = MoodleCourseSubject.objects.get(moodle_course_id='99001')
        self.assertEqual(mapping.subject, self.subject)


class ViewTests(FixtureMixin, TestCase):
    def upload(self, content=None, name='icalexport.ics', **data):
        from django.core.files.uploadedfile import SimpleUploadedFile

        payload = content if content is not None else fixture_bytes()
        return self.client.post(reverse('ical_import_list'), {
            'file': SimpleUploadedFile(name, payload, content_type='text/calendar'),
            **data,
        })

    def test_teacher_can_upload_and_reach_the_preview(self):
        self.client.force_login(self.teacher)
        response = self.upload(subject=self.subject.pk)
        draft = IcalImport.objects.get()
        self.assertRedirects(response, reverse('ical_import_detail', args=[draft.pk]))
        self.assertEqual(draft.events.count(), 49)
        self.assertEqual(draft.moodle_course_id, '99001')
        self.assertEqual(draft.created_by, self.teacher)

        page = self.client.get(reverse('ical_import_detail', args=[draft.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Asistencia clases')
        self.assertContains(page, 'Crear las actividades seleccionadas')

    def test_upload_page_lists_only_subjects_offered_and_taught(self):
        self.client.force_login(self.teacher)
        page = self.client.get(reverse('ical_import_list'))
        choices = [subject.pk for subject in page.context['form'].fields['subject'].queryset]
        self.assertEqual(choices, [self.subject.pk])

    def test_oversized_file_is_rejected(self):
        self.client.force_login(self.teacher)
        response = self.upload(content=b'x' * (ical_import.MAX_UPLOAD_BYTES + 1), subject=self.subject.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('2 MB', str(response.context['form'].errors['file']))
        self.assertFalse(IcalImport.objects.exists())

    def test_non_icalendar_file_is_rejected(self):
        self.client.force_login(self.teacher)
        response = self.upload(content=b'nombre;codigo\nA;1\n', name='datos.csv', subject=self.subject.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('iCalendar', str(response.context['form'].errors['file']))
        self.assertFalse(IcalImport.objects.exists())

    def test_calendar_without_events_is_rejected(self):
        self.client.force_login(self.teacher)
        response = self.upload(content=calendar_with().encode(), subject=self.subject.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('ningún evento', str(response.context['form'].errors['file']))

    def test_upload_without_subject_and_without_mapping_asks_for_one(self):
        self.client.force_login(self.teacher)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Elige la asignatura', str(response.context['form'].errors['subject']))

    def test_remembered_mapping_is_used_when_no_subject_is_chosen(self):
        MoodleCourseSubject.objects.create(moodle_course_id='99001', subject=self.subject)
        self.client.force_login(self.teacher)
        response = self.upload()
        draft = IcalImport.objects.get()
        self.assertRedirects(response, reverse('ical_import_detail', args=[draft.pk]))
        self.assertEqual(draft.subject, self.subject)

    def test_preview_toggles_are_persisted(self):
        self.client.force_login(self.teacher)
        self.upload(subject=self.subject.pk)
        draft = IcalImport.objects.get()
        groups = {group.summary: group for group in group_events(list(draft.events.all()))}
        lessons = groups['Asistencia clases']
        seminar = groups['1º Seminario evaluable']

        data = {
            f'tipo_{lessons.group_id}': str(self.tipo.pk),
            f'porcentaje_{lessons.group_id}': '0',
            f'tipo_{seminar.group_id}': str(self.tipo_examen.pk),
            f'evaluable_{seminar.group_id}': 'on',
            f'porcentaje_{seminar.group_id}': '30',
        }
        # Select the first three lessons of the large group and keep the seminar.
        for event in lessons.events[:3]:
            data[f'event_{event.pk}'] = 'on'
        data[f'event_{seminar.events[0].pk}'] = 'on'
        for summary, group in groups.items():
            data.setdefault(f'tipo_{group.group_id}', str(self.tipo.pk))
            data.setdefault(f'porcentaje_{group.group_id}', '0')

        response = self.client.post(reverse('ical_import_detail', args=[draft.pk]), data)
        self.assertRedirects(response, reverse('ical_import_detail', args=[draft.pk]))

        self.assertEqual(draft.events.filter(selected=True, summary='Asistencia clases').count(), 3)
        seminar_event = draft.events.get(summary='1º Seminario evaluable')
        self.assertTrue(seminar_event.selected)
        self.assertTrue(seminar_event.evaluable)
        self.assertEqual(seminar_event.porcentaje_evaluacion, Decimal('30.00'))
        self.assertEqual(seminar_event.tipo_actividad, self.tipo_examen)
        self.assertEqual(draft.events.filter(summary='2º seminario evaluable', selected=True).count(), 0)

    def test_apply_from_the_view_reports_counts_and_creates_activities(self):
        self.client.force_login(self.teacher)
        self.upload(subject=self.subject.pk)
        draft = IcalImport.objects.get()
        draft.events.update(selected=False)
        draft.events.filter(summary='1º Seminario evaluable').update(selected=True, tipo_actividad=self.tipo)

        response = self.client.post(reverse('ical_import_apply', args=[draft.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 actividades creadas')
        self.assertEqual(Actividad.objects.count(), 1)

    def test_draft_can_be_deleted_while_it_is_a_draft(self):
        self.client.force_login(self.teacher)
        self.upload(subject=self.subject.pk)
        draft = IcalImport.objects.get()
        response = self.client.post(reverse('ical_import_delete', args=[draft.pk]))
        self.assertRedirects(response, reverse('ical_import_list'))
        self.assertFalse(IcalImport.objects.exists())

    def test_applied_import_cannot_be_deleted(self):
        self.client.force_login(self.teacher)
        self.upload(subject=self.subject.pk)
        draft = IcalImport.objects.get()
        draft.events.update(selected=False)
        draft.events.filter(summary='1º Seminario evaluable').update(selected=True, tipo_actividad=self.tipo)
        apply_import(draft, self.teacher)
        self.client.post(reverse('ical_import_delete', args=[draft.pk]))
        self.assertTrue(IcalImport.objects.exists())

    def test_students_cannot_reach_the_import_pages(self):
        self.client.force_login(self.student)
        for url in (reverse('ical_import_list'),):
            response = self.client.get(url)
            self.assertIn(response.status_code, (302, 403))

    def test_a_teacher_cannot_open_another_teachers_import(self):
        draft = self.make_draft()
        intruder = CustomUser.objects.create_user(
            username='ical_other', email='ical_other@unex.es', password=PASSWORD,
            role=CustomUser.ROLE_TEACHER,
        )
        self.client.force_login(intruder)
        response = self.client.get(reverse('ical_import_detail', args=[draft.pk]))
        self.assertEqual(response.status_code, 403)

    def test_mutating_views_require_post(self):
        self.client.force_login(self.teacher)
        draft = self.make_draft()
        for name in ('ical_import_apply', 'ical_import_delete'):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name, args=[draft.pk])).status_code, 405)

    def test_teacher_dashboard_links_to_the_importer(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertContains(response, reverse('ical_import_list'))
