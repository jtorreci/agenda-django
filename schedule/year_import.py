"""Import activities from a previous academic year into the active one."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from academics.models import AcademicYear, offered_subjects

from .models import Actividad, ActividadGrupo, LogActividad

# 52 weeks keeps the weekday: an activity on a Tuesday lands on a Tuesday.
YEAR_SHIFT = timedelta(weeks=52)


class ImportRefused(Exception):
    """The activity cannot be imported; the message is shown to the user."""


def shift_one_year(value):
    """Shift a datetime by 52 weeks, keeping the local wall-clock time across DST."""
    if value is None:
        return None
    if timezone.is_naive(value):
        return value + YEAR_SHIFT
    tz = timezone.get_current_timezone()
    local = timezone.localtime(value, tz).replace(tzinfo=None)
    return timezone.make_aware(local + YEAR_SHIFT, tz)


def user_can_import(user, activity):
    """Same rule as the copy views: the user teaches one of the activity's subjects."""
    return activity.asignaturas.filter(id__in=user.subjects.values('id')).exists()


def imported_source_ids(activities, target_year):
    """Ids of ``activities`` that already have a copy in ``target_year``."""
    if target_year is None:
        return set()
    return set(
        Actividad.objects.filter(
            academic_year=target_year, copied_from__in=activities
        ).values_list('copied_from_id', flat=True)
    )


def import_activity(source, user):
    """Copy ``source`` into the active academic year and return the new activity.

    The copy keeps every field and group, shifts dates by 52 weeks, keeps only the
    subjects offered in the active year, is not approved and records its source.
    Raises :class:`ImportRefused` when the import is not possible.
    """
    target = AcademicYear.get_active()
    if target is None:
        raise ImportRefused('No hay ningún curso académico activo al que traer la actividad.')
    if source.academic_year_id == target.pk:
        raise ImportRefused(f'La actividad "{source.nombre}" ya pertenece al curso actual.')
    if not source.es_visible():
        raise ImportRefused(f'La actividad "{source.nombre}" no está visible y no se puede traer.')
    if Actividad.objects.filter(copied_from=source, academic_year=target).exists():
        raise ImportRefused(f'La actividad "{source.nombre}" ya se trajo al curso {target.code}.')

    subjects = list(offered_subjects(target, source.asignaturas.all()))
    if not subjects:
        raise ImportRefused(
            f'Ninguna asignatura de "{source.nombre}" se oferta en el curso {target.code}; '
            'no se puede traer la actividad.'
        )

    try:
        with transaction.atomic():
            copy = Actividad(
                nombre=source.nombre,
                tipo_actividad=source.tipo_actividad,
                academic_year=target,
                copied_from=source,
                estado=Actividad.ESTADO_VISIBLE,
                fecha_inicio=shift_one_year(source.fecha_inicio),
                fecha_fin=shift_one_year(source.fecha_fin),
                descripcion=source.descripcion,
                evaluable=source.evaluable,
                porcentaje_evaluacion=source.porcentaje_evaluacion,
                no_recuperable=source.no_recuperable,
            )
            copy.save()
            # save() applies the automatic approval rule to new activities; an
            # imported activity must always be reviewed again, so force it off.
            Actividad.objects.filter(pk=copy.pk).update(aprobada=False)
            copy.aprobada = False
            copy.asignaturas.set(subjects)

            for grupo in source.grupos.all():
                ActividadGrupo.objects.create(
                    actividad=copy,
                    nombre_grupo=grupo.nombre_grupo,
                    fecha_inicio=shift_one_year(grupo.fecha_inicio),
                    fecha_fin=shift_one_year(grupo.fecha_fin),
                    descripcion=grupo.descripcion,
                    lugar=grupo.lugar,
                    orden=grupo.orden,
                )

            LogActividad.objects.create(
                object_type='actividad',
                object_name=copy.nombre,
                object_id=copy.id,
                actividad=copy,
                usuario=user,
                tipo_log='Creation',
                details=(
                    f'Actividad traída al curso {target.code} desde la actividad {source.pk} '
                    f'del curso {source.academic_year.code}'
                ),
            )
    except IntegrityError:
        # A concurrent request imported the same source first.
        raise ImportRefused(f'La actividad "{source.nombre}" ya se trajo al curso {target.code}.')
    return copy
