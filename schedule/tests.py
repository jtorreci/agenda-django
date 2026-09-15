import json
import uuid
from datetime import date, datetime, timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AcademicYear, Asignatura, NoActiveAcademicYear, SubjectOffering, Titulacion
from users.models import CustomUser

from .forms import UnifiedActivityForm
from .models import Actividad, ActividadGrupo, ActividadVersion, LogActividad, TipoActividad, VistaCalendario

PASSWORD = 'years-test-password-1'


def local(*args):
    return timezone.make_aware(datetime(*args), timezone.get_current_timezone())


class MigrationBackfillTests(TransactionTestCase):
    before = [
        ('schedule', '0011_actividad_estado_alter_actividad_activa'),
        ('academics', '0006_catalogue_plan_override'),
    ]
    after = [
        ('schedule', '0014_actividad_academic_year_not_null'),
        ('academics', '0006_catalogue_plan_override'),
    ]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        self.apps = executor.loader.project_state(self.before).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def migrate_forward(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.after)
        return executor.loader.project_state(self.after).apps

    def create_legacy_activity(self):
        TipoActividad = self.apps.get_model('schedule', 'TipoActividad')
        Actividad = self.apps.get_model('schedule', 'Actividad')
        tipo = TipoActividad.objects.create(nombre='Examen')
        return Actividad.objects.create(
            nombre='Legacy', tipo_actividad=tipo,
            fecha_inicio=local(2026, 1, 10, 9), fecha_fin=local(2026, 1, 10, 11),
        )

    def test_existing_activities_get_archived_2025_26(self):
        self.apps.get_model('academics', 'AcademicYear').objects.create(
            code='2026-27', starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31), state='active'
        )
        legacy = self.create_legacy_activity()

        apps = self.migrate_forward()

        activity = apps.get_model('schedule', 'Actividad').objects.select_related('academic_year').get(pk=legacy.pk)
        self.assertEqual(activity.academic_year.code, '2025-26')
        self.assertEqual(activity.academic_year.state, 'archived')
        self.assertEqual(activity.academic_year.starts_on, date(2025, 9, 1))
        self.assertEqual(activity.academic_year.ends_on, date(2026, 8, 31))
        years = dict(apps.get_model('academics', 'AcademicYear').objects.values_list('code', 'state'))
        self.assertEqual(years, {'2025-26': 'archived', '2026-27': 'active'})

    def test_existing_draft_2025_26_is_archived(self):
        self.apps.get_model('academics', 'AcademicYear').objects.create(
            code='2025-26', starts_on=date(2025, 9, 1), ends_on=date(2026, 8, 31), state='draft'
        )
        self.create_legacy_activity()

        apps = self.migrate_forward()

        self.assertEqual(apps.get_model('academics', 'AcademicYear').objects.get(code='2025-26').state, 'archived')

    def test_empty_database_gets_no_legacy_year(self):
        apps = self.migrate_forward()
        self.assertFalse(apps.get_model('academics', 'AcademicYear').objects.exists())


class YearFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.past = AcademicYear.objects.create(
            code='2025-26', starts_on=date(2025, 9, 1), ends_on=date(2026, 8, 31),
            state=AcademicYear.STATE_ARCHIVED,
        )
        cls.active = AcademicYear.objects.create(
            code='2026-27', starts_on=date(2026, 9, 1), ends_on=date(2027, 8, 31),
            state=AcademicYear.STATE_ACTIVE,
        )
        cls.draft = AcademicYear.objects.create(
            code='2027-28', starts_on=date(2027, 9, 1), ends_on=date(2028, 8, 31)
        )
        cls.plan = Titulacion.objects.create(nombre='Grado', codigo_plan='G1')
        cls.offered = Asignatura.objects.create(
            nombre='Offered', codigo_asignatura='S1', titulacion=cls.plan, curso=1, semestre=1
        )
        cls.unoffered = Asignatura.objects.create(
            nombre='Unoffered', codigo_asignatura='S2', titulacion=cls.plan, curso=1, semestre=1
        )
        SubjectOffering.objects.create(academic_year=cls.active, subject=cls.offered, curricular_year=1, semester=1)
        SubjectOffering.objects.create(academic_year=cls.past, subject=cls.unoffered, curricular_year=1, semester=1)
        cls.tipo = TipoActividad.objects.create(nombre='Examen')

        cls.teacher = cls.make_user('teacher', CustomUser.ROLE_TEACHER, cls.offered, cls.unoffered)
        cls.other_teacher = cls.make_user('other', CustomUser.ROLE_TEACHER)
        cls.coordinator = cls.make_user('coordinator', CustomUser.ROLE_COORDINATOR)
        cls.student = cls.make_user('student', CustomUser.ROLE_STUDENT, cls.offered)
        cls.plan.coordinador = cls.coordinator
        cls.plan.save()

        cls.past_activity = cls.make_activity(cls.past, 'Past exam', cls.offered, cls.unoffered)
        cls.active_activity = cls.make_activity(cls.active, 'Active exam', cls.offered, start=local(2026, 10, 6, 9))

    @staticmethod
    def make_user(name, role, *subjects):
        user = CustomUser.objects.create_user(username=name, email=f'{name}@unex.es', password=PASSWORD, role=role)
        user.subjects.set(subjects)
        return user

    @classmethod
    def make_activity(cls, year, name, *subjects, start=None, groups=(), **fields):
        start = start or local(2025, 10, 7, 9, 30)  # a Tuesday
        activity = Actividad.objects.create(
            nombre=name, tipo_actividad=cls.tipo, academic_year=year,
            fecha_inicio=start, fecha_fin=start + timedelta(hours=2), descripcion='desc', **fields
        )
        activity.asignaturas.set(subjects)
        for order, (group_name, group_start) in enumerate(groups, 1):
            ActividadGrupo.objects.create(
                actividad=activity, nombre_grupo=group_name, fecha_inicio=group_start,
                fecha_fin=group_start + timedelta(hours=1), lugar=f'Aula {group_name}',
                descripcion=f'G{group_name}', orden=order,
            )
        return activity

    def login(self, user):
        self.client.force_login(user)


class YearSelectorTests(YearFixtureMixin, TestCase):
    def filtered_rows(self, **params):
        query = {'subject_ids': str(self.offered.pk), **params}
        response = self.client.get(reverse('get_filtered_activities'), query)
        self.assertEqual(response.status_code, 200)
        return {row['activity_id']: row for row in response.json()}

    def test_teacher_dashboard_defaults_to_active_year(self):
        self.login(self.teacher)
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.context['selected_academic_year_ids'], [self.active.pk])
        self.assertEqual([y.code for y in response.context['academic_years']], ['2026-27', '2025-26'])
        self.assertEqual(list(response.context['activities']), [self.active_activity])
        self.assertEqual(set(self.filtered_rows()), {self.active_activity.pk})

    def test_teacher_can_select_several_years(self):
        self.login(self.teacher)
        response = self.client.get(reverse('teacher_dashboard'), {'academic_year': [self.past.pk, self.active.pk]})
        self.assertEqual(response.context['selected_academic_year_ids'], [self.past.pk, self.active.pk])
        self.assertTrue(response.context['past_years_selected'])
        self.assertContains(response, reverse('import_subject_activities', args=[self.offered.pk]))

        rows = self.filtered_rows(academic_year=[self.past.pk, self.active.pk])
        self.assertEqual(set(rows), {self.past_activity.pk, self.active_activity.pk})
        past_props = rows[self.past_activity.pk]['extendedProps']
        self.assertEqual(past_props['academic_year'], '2025-26')
        self.assertTrue(past_props['is_read_only'])
        self.assertTrue(past_props['can_import'])
        self.assertFalse(rows[self.active_activity.pk]['extendedProps']['is_read_only'])

    def test_draft_and_unknown_years_are_ignored(self):
        self.login(self.teacher)
        self.assertEqual(set(self.filtered_rows(academic_year=[self.draft.pk, 'x'])), {self.active_activity.pk})
        self.assertEqual(set(self.filtered_rows(academic_year=[self.past.pk])), {self.past_activity.pk})

    def test_coordinator_dashboard_and_calendar_follow_selection(self):
        self.login(self.coordinator)
        response = self.client.get(reverse('coordinator_dashboard'))
        self.assertEqual(list(response.context['active_activities']), [self.active_activity])
        response = self.client.get(
            reverse('coordinator_dashboard'), {'academic_year': [self.past.pk, self.active.pk]}
        )
        self.assertEqual(set(response.context['active_activities']), {self.past_activity, self.active_activity})
        self.assertContains(response, 'data-read-only="true"')

        calendar = self.client.get(reverse('all_activities'), {'academic_year': self.past.pk}).json()
        self.assertEqual({row['activity_id'] for row in calendar}, {self.past_activity.pk})
        calendar = self.client.get(reverse('all_activities')).json()
        self.assertEqual({row['activity_id'] for row in calendar}, {self.active_activity.pk})


class ReadOnlyEnforcementTests(YearFixtureMixin, TestCase):
    def assert_forbidden(self, response):
        self.assertEqual(response.status_code, 403)

    def test_edit_forms_reject_past_year_activities(self):
        self.login(self.teacher)
        payload = {
            'nombre': 'Hacked', 'asignaturas': [self.offered.pk], 'tipo_actividad': self.tipo.pk,
            'porcentaje_evaluacion': '0',
            'grupos_data': json.dumps(
                [{'grupo': 'A', 'fecha_inicio': '2025-10-07T09:00', 'fecha_fin': '2025-10-07T10:00'}]
            ),
            'fecha_inicio': '2025-10-07T09:00', 'fecha_fin': '2025-10-07T10:00',
        }
        for name in ('unified_activity_edit', 'activity_edit', 'activity_check_edit'):
            with self.subTest(view=name):
                url = reverse(name, args=[self.past_activity.pk])
                self.assert_forbidden(self.client.get(url))
                response = self.client.post(url, payload)
                self.assertContains(response, 'solo lectura', status_code=403)
        self.past_activity.refresh_from_db()
        self.assertEqual(self.past_activity.nombre, 'Past exam')
        self.assertEqual(Actividad.objects.count(), 2)

    def test_multi_group_edit_rejects_past_year_activities(self):
        grupo_id = uuid.uuid4()
        Actividad.objects.filter(pk=self.past_activity.pk).update(grupo_id=grupo_id)
        self.login(self.teacher)
        self.assert_forbidden(self.client.post(reverse('multi_group_activity_edit', args=[grupo_id]), {}))
        self.assertTrue(Actividad.objects.get(pk=self.past_activity.pk).activa)

    def test_delete_rejects_past_year_activities(self):
        self.login(self.teacher)
        self.assert_forbidden(self.client.get(reverse('activity_delete', args=[self.past_activity.pk])))
        self.assert_forbidden(self.client.post(reverse('activity_delete', args=[self.past_activity.pk])))
        self.assertTrue(Actividad.objects.get(pk=self.past_activity.pk).activa)
        # Active-year activities are still deletable.
        response = self.client.post(reverse('activity_delete', args=[self.active_activity.pk]))
        self.assertEqual(response.status_code, 302)

    def test_delete_misassigned_and_archive_reject_past_year_activities(self):
        self.login(self.coordinator)
        self.assert_forbidden(self.client.post(reverse('delete_misassigned_activity', args=[self.past_activity.pk])))
        self.assertTrue(Actividad.objects.filter(pk=self.past_activity.pk).exists())
        Actividad.objects.filter(pk=self.past_activity.pk).update(estado=Actividad.ESTADO_BORRADA, activa=False)
        response = self.client.post(
            reverse('archivar_actividad_ajax'), json.dumps({'actividad_id': self.past_activity.pk}),
            content_type='application/json',
        )
        self.assert_forbidden(response)
        self.assertEqual(Actividad.objects.get(pk=self.past_activity.pk).estado, Actividad.ESTADO_BORRADA)

    def test_approval_toggles_reject_past_year_activities(self):
        approved_before = Actividad.objects.get(pk=self.past_activity.pk).aprobada
        self.login(self.coordinator)
        self.assert_forbidden(self.client.post(reverse('toggle_activity_approval', args=[self.past_activity.pk])))
        response = self.client.post(
            reverse('toggle_activity_approval_from_dashboard', args=[self.past_activity.pk]),
            json.dumps({'aprobada': not approved_before}), content_type='application/json',
        )
        self.assert_forbidden(response)
        self.assertFalse(response.json()['success'])
        self.assertEqual(Actividad.objects.get(pk=self.past_activity.pk).aprobada, approved_before)

    def test_reactivate_rejects_past_year_activities(self):
        Actividad.objects.filter(pk=self.past_activity.pk).update(estado=Actividad.ESTADO_BORRADA, activa=False)
        self.login(self.coordinator)
        self.assert_forbidden(self.client.post(reverse('reactivate_activity', args=[self.past_activity.pk])))
        self.assertFalse(Actividad.objects.get(pk=self.past_activity.pk).activa)

    def test_restore_version_rejects_past_year_activities(self):
        version = ActividadVersion.objects.create(
            actividad_original=self.past_activity, version_numero=1, modificada_por=self.teacher,
            nombre='Old name', fecha_inicio=self.past_activity.fecha_inicio, fecha_fin=self.past_activity.fecha_fin,
        )
        self.login(self.teacher)
        url = reverse('activity_restore_version', args=[self.past_activity.pk, version.pk])
        self.assert_forbidden(self.client.get(url))
        self.assert_forbidden(self.client.post(url))
        self.assertEqual(Actividad.objects.get(pk=self.past_activity.pk).nombre, 'Past exam')
        detail = self.client.get(reverse('activity_version_detail', args=[self.past_activity.pk, version.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, url)

    def test_viewing_pdf_and_history_stay_available(self):
        self.login(self.teacher)
        detail = self.client.get(reverse('activity_detail_view', args=[self.past_activity.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, reverse('activity_check_edit', args=[self.past_activity.pk]))
        self.assertContains(detail, reverse('import_activity_to_current_year', args=[self.past_activity.pk]))
        pdf = self.client.get(reverse('activity_pdf_convocatoria', args=[self.past_activity.pk]))
        self.assertEqual(pdf.status_code, 200)
        history = self.client.get(reverse('activity_version_history', args=[self.past_activity.pk]))
        self.assertEqual(history.status_code, 200)
        self.assertNotContains(history, reverse('activity_check_edit', args=[self.past_activity.pk]))
        readonly = self.client.get(reverse('activity_details_readonly', args=[self.past_activity.pk]))
        self.assertEqual(readonly.status_code, 200)


class ImportActivityTests(YearFixtureMixin, TestCase):
    def import_url(self, activity):
        return reverse('import_activity_to_current_year', args=[activity.pk])

    def test_import_copies_activity_into_active_year(self):
        source = self.make_activity(
            self.past, 'Lab', self.offered, self.unoffered,
            groups=[('A', local(2025, 10, 7, 9, 30)), ('B', local(2025, 10, 9, 16))],
        )
        self.assertTrue(source.aprobada)  # not evaluable: auto-approved on creation
        self.login(self.teacher)

        response = self.client.post(self.import_url(source))

        self.assertRedirects(response, reverse('teacher_dashboard'), fetch_redirect_response=False)
        copy = Actividad.objects.get(copied_from=source)
        self.assertEqual(copy.academic_year, self.active)
        self.assertEqual(copy.nombre, 'Lab')
        self.assertEqual(copy.descripcion, 'desc')
        self.assertFalse(copy.aprobada)
        self.assertEqual(list(copy.asignaturas.all()), [self.offered])
        self.assertEqual(copy.fecha_inicio - source.fecha_inicio, timedelta(weeks=52))
        local_start = timezone.localtime(copy.fecha_inicio)
        self.assertEqual(local_start.replace(tzinfo=None), datetime(2026, 10, 6, 9, 30))
        self.assertEqual(local_start.weekday(), timezone.localtime(source.fecha_inicio).weekday())
        groups = list(copy.grupos.values_list('nombre_grupo', 'lugar', 'descripcion', 'orden'))
        self.assertEqual(groups, [('A', 'Aula A', 'GA', 1), ('B', 'Aula B', 'GB', 2)])
        self.assertEqual(
            [timezone.localtime(g.fecha_inicio) for g in copy.grupos.all()],
            [local(2026, 10, 6, 9, 30), local(2026, 10, 8, 16)],
        )
        self.assertTrue(LogActividad.objects.filter(actividad=copy, tipo_log='Creation').exists())
        source.refresh_from_db()
        self.assertEqual(source.academic_year, self.past)
        self.assertEqual(source.grupos.count(), 2)

    def test_import_keeps_local_time_across_daylight_saving_change(self):
        # 2026-10-26 is winter time; 52 weeks later (2027-10-25) is still summer time.
        source = self.make_activity(self.past, 'DST', self.offered, start=local(2026, 10, 26, 10))
        self.login(self.teacher)
        self.client.post(self.import_url(source))
        copy = Actividad.objects.get(copied_from=source)
        self.assertEqual(timezone.localtime(copy.fecha_inicio).replace(tzinfo=None), datetime(2027, 10, 25, 10))

    def test_same_source_cannot_be_imported_twice(self):
        self.login(self.teacher)
        self.client.post(self.import_url(self.past_activity))
        response = self.client.post(self.import_url(self.past_activity), follow=True)
        self.assertEqual(Actividad.objects.filter(copied_from=self.past_activity).count(), 1)
        self.assertContains(response, 'ya se trajo')

        rows = self.client.get(
            reverse('get_filtered_activities'), {'subject_ids': self.offered.pk, 'academic_year': self.past.pk}
        ).json()
        props = rows[0]['extendedProps']
        self.assertTrue(props['already_imported'])
        self.assertFalse(props['can_import'])
        detail = self.client.get(reverse('activity_detail_view', args=[self.past_activity.pk]))
        self.assertContains(detail, 'Ya traída')
        self.assertNotContains(detail, self.import_url(self.past_activity))

    def test_import_refused_when_no_subject_is_offered(self):
        source = self.make_activity(self.past, 'Only unoffered', self.unoffered)
        self.login(self.teacher)
        response = self.client.post(self.import_url(source), follow=True)
        self.assertFalse(Actividad.objects.filter(copied_from=source).exists())
        self.assertContains(response, 'Ninguna asignatura')

    def test_import_refused_without_active_year(self):
        AcademicYear.objects.filter(pk=self.active.pk).update(state=AcademicYear.STATE_ARCHIVED)
        self.login(self.teacher)
        response = self.client.post(self.import_url(self.past_activity), follow=True)
        self.assertFalse(Actividad.objects.filter(copied_from=self.past_activity).exists())
        self.assertContains(response, 'No hay ningún curso académico activo')

    def test_active_year_activity_cannot_be_imported(self):
        self.login(self.teacher)
        self.client.post(self.import_url(self.active_activity))
        self.assertFalse(Actividad.objects.filter(copied_from=self.active_activity).exists())

    def test_import_requires_post_and_subject_permission(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.import_url(self.past_activity)).status_code, 405)
        self.login(self.other_teacher)
        self.assertEqual(self.client.post(self.import_url(self.past_activity)).status_code, 403)
        self.assertFalse(Actividad.objects.filter(copied_from=self.past_activity).exists())

    def test_import_redirects_to_safe_next_only(self):
        self.login(self.teacher)
        next_url = reverse('teacher_dashboard') + f'?academic_year={self.past.pk}'
        response = self.client.post(self.import_url(self.past_activity), {'next': next_url})
        self.assertEqual(response['Location'], next_url)
        other = self.make_activity(self.past, 'Other', self.offered)
        response = self.client.post(self.import_url(other), {'next': 'https://evil.example/'})
        self.assertEqual(response['Location'], reverse('teacher_dashboard'))

    def test_bulk_import_of_subject(self):
        second = self.make_activity(self.past, 'Second', self.offered)
        deleted = self.make_activity(self.past, 'Deleted', self.offered, estado=Actividad.ESTADO_BORRADA)
        unrelated = self.make_activity(self.past, 'Unrelated', self.unoffered)
        self.login(self.teacher)
        self.client.post(self.import_url(self.past_activity))

        url = reverse('import_subject_activities', args=[self.offered.pk])
        response = self.client.post(url, {'academic_year': [self.past.pk, self.active.pk]}, follow=True)

        self.assertEqual(Actividad.objects.filter(copied_from=second).count(), 1)
        self.assertEqual(Actividad.objects.filter(copied_from=self.past_activity).count(), 1)
        self.assertFalse(Actividad.objects.filter(copied_from__in=[deleted, unrelated, self.active_activity]).exists())
        self.assertFalse(Actividad.objects.get(copied_from=second).aprobada)
        self.assertContains(response, '1 actividad(es) de')
        self.assertContains(response, 'ya se habían traído')

    def test_bulk_import_requires_teaching_the_subject(self):
        self.login(self.other_teacher)
        url = reverse('import_subject_activities', args=[self.offered.pk])
        self.assertEqual(self.client.post(url, {'academic_year': [self.past.pk]}).status_code, 403)
        self.assertEqual(Actividad.objects.count(), 2)

    def test_imported_copy_is_editable_and_copyable(self):
        self.login(self.teacher)
        self.client.post(self.import_url(self.past_activity))
        copy = Actividad.objects.get(copied_from=self.past_activity)
        self.assertEqual(self.client.get(reverse('unified_activity_edit', args=[copy.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('activity_delete', args=[copy.pk])).status_code, 302)


class StudentActiveYearTests(YearFixtureMixin, TestCase):
    def test_student_dashboard_and_calendar_only_show_active_year(self):
        self.login(self.student)
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(list(response.context['activities']), [self.active_activity])
        events = self.client.get(reverse('student_calendar_events')).json()
        self.assertEqual([event['id'] for event in events], [self.active_activity.pk])

    def test_ical_feeds_only_export_active_year(self):
        subject_feed = VistaCalendario.objects.create(nombre='Mine', usuario=self.student)
        subject_feed.asignaturas.set([self.offered])
        all_feed = VistaCalendario.objects.create(nombre='All', usuario=self.coordinator)
        type_feed = VistaCalendario.objects.create(nombre='Types', usuario=self.coordinator)
        type_feed.tipos_actividad.set([self.tipo])
        for feed in (subject_feed, all_feed, type_feed):
            with self.subTest(feed=feed.nombre):
                body = self.client.get(reverse('ical_feed', args=[feed.token])).content.decode()
                self.assertIn('Active exam', body)
                self.assertNotIn('Past exam', body)

    def test_teacher_student_view_only_shows_active_year(self):
        self.login(self.teacher)
        response = self.client.get(reverse('teacher_student_view'))
        self.assertEqual(list(response.context['activities']), [self.active_activity])

    def test_students_see_nothing_without_active_year(self):
        AcademicYear.objects.filter(pk=self.active.pk).update(state=AcademicYear.STATE_ARCHIVED)
        self.login(self.student)
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['activities']), [])
        self.assertEqual(self.client.get(reverse('student_calendar_events')).json(), [])


class NewActivityFormTests(YearFixtureMixin, TestCase):
    def payload(self, *subjects):
        return {
            'nombre': 'New', 'asignaturas': [s.pk for s in subjects], 'tipo_actividad': self.tipo.pk,
            'porcentaje_evaluacion': '0',
            'grupos_data': json.dumps(
                [{'grupo': 'A', 'fecha_inicio': '2026-10-06T09:00', 'fecha_fin': '2026-10-06T10:00'}]
            ),
        }

    def test_form_only_offers_subjects_offered_in_active_year(self):
        form = UnifiedActivityForm(user=self.teacher)
        self.assertEqual(list(form.fields['asignaturas'].queryset), [self.offered])
        self.assertFalse(UnifiedActivityForm(self.payload(self.unoffered), user=self.teacher).is_valid())

    def test_new_activity_gets_active_year(self):
        self.login(self.teacher)
        response = self.client.get(
            reverse('unified_activity_new'), {'subjects': f'{self.offered.pk},{self.unoffered.pk}'}
        )
        self.assertEqual(list(response.context['form'].fields['asignaturas'].queryset), [self.offered])
        response = self.client.post(reverse('unified_activity_new'), self.payload(self.offered))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Actividad.objects.get(nombre='New').academic_year, self.active)

    def test_creation_fails_clearly_without_active_year(self):
        AcademicYear.objects.filter(pk=self.active.pk).update(state=AcademicYear.STATE_ARCHIVED)
        self.login(self.teacher)
        response = self.client.post(reverse('unified_activity_new'), self.payload(self.offered))
        self.assertContains(response, 'No hay ningún curso académico activo')
        self.assertFalse(Actividad.objects.filter(nombre='New').exists())
        with self.assertRaises(NoActiveAcademicYear):
            Actividad.objects.create(
                nombre='Direct', tipo_actividad=self.tipo,
                fecha_inicio=local(2026, 1, 1), fecha_fin=local(2026, 1, 1, 1),
            )

    def test_cascading_subject_endpoint_only_returns_offered_subjects(self):
        self.login(self.teacher)
        response = self.client.get(
            reverse('get_asignaturas'), {'titulacion_id': self.plan.pk, 'curso': 1, 'semestre': 1}
        )
        self.assertEqual([row['id'] for row in response.json()], [self.offered.pk])
