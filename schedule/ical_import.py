"""Import activities from a Moodle course calendar export (.ics).

The Moodle export of a course calendar carries one VEVENT per event with a UID,
a SUMMARY, an optional DESCRIPTION, UTC DTSTART/DTEND and CATEGORIES holding the
numeric Moodle course id. There is no subject name, no location and no activity
type, so the teacher chooses the subject when uploading and the activity type
per group of repeated events in the preview.

The flow mirrors the catalogue importer (``academics.catalogue_import``): parse,
stage a draft the user reviews and edits, then apply it in one transaction.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from icalendar import Calendar

from academics.models import AcademicYear, Asignatura, offered_subjects

from .models import (
    Actividad,
    IcalImport,
    IcalImportEvent,
    LogActividad,
    MoodleCourseSubject,
)

MAX_UPLOAD_BYTES = 2 * 1024 * 1024

# Groups of this size or larger are unselected by default: a whole term of
# "Asistencia clases" is rarely wanted, a one-off seminar almost always is.
LARGE_GROUP_SIZE = 5

UNSUPPORTED_RECURRENCE = 'repetición no soportada'


class IcalImportRefused(ValidationError):
    """The calendar or the import cannot be processed; messages are shown as-is."""


@dataclass
class ParsedEvent:
    """One VEVENT, already converted to the project timezone."""

    uid: str
    summary: str
    description: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    zero_duration: bool = False
    unsupported_reason: str = ''

    @property
    def group_key(self):
        return normalize_summary(self.summary)


@dataclass
class ParsedCalendar:
    events: list = field(default_factory=list)
    moodle_course_id: str = ''


def normalize_summary(value):
    """Case- and whitespace-insensitive grouping key for a summary."""
    return ' '.join((value or '').split()).casefold()


def _text(component, name, default=''):
    value = component.get(name)
    if value is None:
        return default
    return str(value)


def _course_ids(component):
    categories = component.get('CATEGORIES')
    if categories is None:
        return []
    cats = getattr(categories, 'cats', None)
    if cats is None:
        return [str(categories).strip()] if str(categories).strip() else []
    return [str(cat).strip() for cat in cats if str(cat).strip()]


def _localize(value, tz):
    """Return an aware datetime in ``tz`` for a DATE-TIME property value."""
    if timezone.is_naive(value):
        return timezone.make_aware(value, tz)
    return value.astimezone(tz)


def _end_of_day(day, tz):
    return timezone.make_aware(datetime.combine(day, time(23, 59)), tz)


def _parse_event(component, tz):
    """Turn one VEVENT into a ParsedEvent, or None when it carries no date."""
    uid = _text(component, 'UID').strip()
    start_property = component.get('DTSTART')
    if not uid or start_property is None:
        return None

    raw_start = start_property.dt
    end_property = component.get('DTEND')
    raw_end = end_property.dt if end_property is not None else None

    if isinstance(raw_start, datetime):
        all_day = False
        starts_at = _localize(raw_start, tz)
        if isinstance(raw_end, datetime):
            ends_at = _localize(raw_end, tz)
        else:
            ends_at = starts_at
    elif isinstance(raw_start, date):
        # DATE-only values are whole days: 00:00 to 23:59 local time. A DATE
        # DTEND is exclusive in iCalendar, so the last day is DTEND - 1 day.
        all_day = True
        starts_at = timezone.make_aware(datetime.combine(raw_start, time(0, 0)), tz)
        last_day = raw_start
        if isinstance(raw_end, date) and not isinstance(raw_end, datetime):
            last_day = max(raw_end - timedelta(days=1), raw_start)
        ends_at = _end_of_day(last_day, tz)
    else:
        return None

    if ends_at < starts_at:
        ends_at = starts_at

    return ParsedEvent(
        uid=uid,
        summary=' '.join(_text(component, 'SUMMARY').split())[:255] or '(sin título)',
        description=_text(component, 'DESCRIPTION').strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        zero_duration=not all_day and ends_at == starts_at,
        unsupported_reason=UNSUPPORTED_RECURRENCE if 'RRULE' in component else '',
    )


def parse_calendar(source):
    """Parse a Moodle .ics export.

    ``source`` may be bytes, text or a file-like object. VTODO and VJOURNAL
    components are ignored. Raises :class:`IcalImportRefused` when the file is
    not an iCalendar file or carries no usable event.
    """
    data = source.read() if hasattr(source, 'read') else source
    if isinstance(data, str):
        data = data.encode('utf-8')
    if not data.strip():
        raise IcalImportRefused('El fichero está vacío.')

    try:
        calendar = Calendar.from_ical(data)
    except (ValueError, UnicodeDecodeError):
        raise IcalImportRefused('El fichero no es un calendario iCalendar válido.')
    if calendar.name != 'VCALENDAR':
        raise IcalImportRefused('El fichero no es un calendario iCalendar válido.')

    tz = timezone.get_current_timezone()
    events, seen, course_ids = [], set(), []
    for component in calendar.walk('VEVENT'):
        event = _parse_event(component, tz)
        if event is None or event.uid in seen:
            continue
        seen.add(event.uid)
        events.append(event)
        course_ids.extend(_course_ids(component))

    if not events:
        raise IcalImportRefused('El calendario no contiene ningún evento.')

    events.sort(key=lambda item: (item.starts_at, item.uid))
    return ParsedCalendar(events=events, moodle_course_id=_dominant(course_ids))


def _dominant(values):
    """Most frequent value, or '' when there is none."""
    if not values:
        return ''
    return Counter(values).most_common(1)[0][0][:64]


# -- draft -------------------------------------------------------------------


def importable_subjects(user, academic_year):
    """Subjects ``user`` may import into for ``academic_year``.

    Admins reach every offered subject; coordinators also reach the subjects of
    the degrees they coordinate; everybody else only the subjects they teach.
    """
    if academic_year is None:
        return Asignatura.objects.none()
    base = Asignatura.objects.all()
    if not (user.role == user.ROLE_ADMIN or user.is_superuser):
        allowed = set(user.subjects.values_list('id', flat=True))
        if user.role == user.ROLE_COORDINATOR:
            allowed.update(
                Asignatura.objects.filter(
                    titulacion__in=user.coordinated_titulaciones.all()
                ).values_list('id', flat=True)
            )
        base = base.filter(id__in=allowed)
    return offered_subjects(academic_year, base).select_related('titulacion').order_by('nombre')


def can_import_into(user, subject, academic_year):
    return importable_subjects(user, academic_year).filter(pk=subject.pk).exists()


def imported_uids(academic_year, uids):
    """UIDs of ``uids`` that already belong to an activity of ``academic_year``."""
    if academic_year is None or not uids:
        return set()
    return set(
        Actividad.objects.filter(academic_year=academic_year, ical_uid__in=list(uids))
        .values_list('ical_uid', flat=True)
    )


def default_selection(events):
    """Default checkbox state per group key: large groups start unselected."""
    sizes = Counter(event.group_key for event in events)
    return {key: size < LARGE_GROUP_SIZE for key, size in sizes.items()}


@transaction.atomic
def build_draft(parsed, subject, academic_year, filename, user):
    """Stage a parsed calendar as a draft import for ``subject``."""
    if academic_year is None or not academic_year.is_active:
        raise IcalImportRefused('Solo se pueden importar actividades en el curso académico activo.')
    if not offered_subjects(academic_year, Asignatura.objects.filter(pk=subject.pk)).exists():
        raise IcalImportRefused(
            f'La asignatura «{subject}» no se oferta en el curso académico {academic_year.code}.'
        )

    ical_import = IcalImport.objects.create(
        academic_year=academic_year,
        subject=subject,
        source_filename=(filename or '')[:255],
        moodle_course_id=parsed.moodle_course_id,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    already = imported_uids(academic_year, [event.uid for event in parsed.events])
    selection = default_selection(parsed.events)
    rows = []
    for event in parsed.events:
        if event.uid in already:
            status, detail, selected = IcalImportEvent.STATUS_DUPLICATE, '', False
        elif event.unsupported_reason:
            status, detail, selected = IcalImportEvent.STATUS_UNSUPPORTED, event.unsupported_reason, False
        else:
            status, detail = IcalImportEvent.STATUS_PENDING, ''
            selected = selection[event.group_key]
        rows.append(IcalImportEvent(
            ical_import=ical_import,
            uid=event.uid[:255],
            summary=event.summary,
            description=event.description,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            all_day=event.all_day,
            zero_duration=event.zero_duration,
            group_key=event.group_key[:255],
            selected=selected,
            status=status,
            status_detail=detail,
        ))
    IcalImportEvent.objects.bulk_create(rows)
    return ical_import


# -- preview -----------------------------------------------------------------


@dataclass
class EventGroup:
    """Events sharing a normalized summary, edited together in the preview."""

    key: str
    summary: str
    events: list

    @property
    def group_id(self):
        """Stable id for form field names: the lowest event id of the group."""
        return min(event.pk for event in self.events)

    @property
    def count(self):
        return len(self.events)

    @property
    def first_date(self):
        return self.events[0].starts_at

    @property
    def last_date(self):
        return self.events[-1].starts_at

    @property
    def selected_count(self):
        return sum(1 for event in self.events if event.selected)

    @property
    def importable_count(self):
        return sum(1 for event in self.events if event.is_importable)

    @property
    def all_selected(self):
        return self.importable_count > 0 and self.selected_count == self.importable_count

    @property
    def tipo_actividad(self):
        """The group's activity type when every event agrees, else None."""
        types = {event.tipo_actividad_id for event in self.events}
        return self.events[0].tipo_actividad if len(types) == 1 else None

    @property
    def evaluable(self):
        return all(event.evaluable for event in self.events)

    @property
    def porcentaje_evaluacion(self):
        values = {event.porcentaje_evaluacion for event in self.events}
        return values.pop() if len(values) == 1 else Decimal('0.00')

    @property
    def missing_type(self):
        return any(event.selected and event.tipo_actividad_id is None for event in self.events)


def group_events(events):
    """Group staged events by normalized summary, ordered by their first date."""
    groups = {}
    for event in sorted(events, key=lambda item: (item.starts_at, item.uid)):
        group = groups.get(event.group_key)
        if group is None:
            groups[event.group_key] = EventGroup(event.group_key, event.summary, [event])
        else:
            group.events.append(event)
    return sorted(groups.values(), key=lambda group: (group.first_date, group.summary))


EDITABLE_FIELDS = ['selected', 'tipo_actividad', 'evaluable', 'porcentaje_evaluacion']


def _parse_percentage(raw):
    try:
        value = Decimal((raw or '0').replace(',', '.'))
    except (ArithmeticError, ValueError):
        return None
    if not value.is_finite() or value < 0 or value > 100:
        return None
    return value.quantize(Decimal('0.01'))


def save_selection(ical_import, data, activity_types):
    """Apply the preview form to the staged events.

    Selection is read per event (``event_<pk>``); the activity type and the
    evaluation settings are read per group (``tipo_<group id>``) and written to
    every event of the group.
    """
    if not ical_import.is_draft:
        raise IcalImportRefused('Solo se pueden editar importaciones en borrador.')

    types = {str(item.pk): item for item in activity_types}
    groups = group_events(list(ical_import.events.all()))
    invalid = []
    changed = []
    for group in groups:
        group_id = group.group_id
        tipo = types.get((data.get(f'tipo_{group_id}') or '').strip())
        evaluable = data.get(f'evaluable_{group_id}') == 'on'
        porcentaje = _parse_percentage(data.get(f'porcentaje_{group_id}')) if evaluable else Decimal('0.00')
        if porcentaje is None:
            invalid.append(group.summary)
            porcentaje = Decimal('0.00')
        for event in group.events:
            if not event.is_importable:
                event.selected = False
                continue
            event.selected = f'event_{event.pk}' in data
            event.tipo_actividad = tipo
            event.evaluable = evaluable
            event.porcentaje_evaluacion = porcentaje
            changed.append(event)

    if invalid:
        raise IcalImportRefused(
            'El porcentaje de evaluación debe estar entre 0 y 100 en: %s. No se ha guardado nada.'
            % ', '.join(sorted(set(invalid))[:5])
        )
    IcalImportEvent.objects.bulk_update(changed, EDITABLE_FIELDS)
    return len(changed)


# -- apply -------------------------------------------------------------------


@dataclass
class ApplyResult:
    created: int = 0
    skipped: int = 0
    failed: int = 0


def _log_details(ical_import, event):
    return (
        f'Actividad importada del calendario del campus virtual '
        f'({ical_import.source_filename or "sin nombre"}, evento {event.uid})'
    )


def apply_import(ical_import, user):
    """Create one activity per selected event. Safe to run twice."""
    with transaction.atomic():
        ical_import = (
            IcalImport.objects.select_for_update()
            .select_related('academic_year', 'subject')
            .get(pk=ical_import.pk)
        )
        academic_year = AcademicYear.get_active()
        if academic_year is None or ical_import.academic_year_id != academic_year.pk:
            raise IcalImportRefused('Solo se pueden importar actividades en el curso académico activo.')
        subject = ical_import.subject
        if not offered_subjects(academic_year, Asignatura.objects.filter(pk=subject.pk)).exists():
            raise IcalImportRefused(
                f'La asignatura «{subject}» no se oferta en el curso académico {academic_year.code}.'
            )
        if not can_import_into(user, subject, academic_year):
            raise IcalImportRefused(f'Ya no impartes la asignatura «{subject}»; no puedes importar en ella.')

        # Events already created keep their selection, so applying twice simply
        # finds them again and counts them as duplicates.
        selected = [
            event for event in ical_import.events.all()
            if event.selected and event.status != IcalImportEvent.STATUS_UNSUPPORTED
        ]
        if not selected:
            raise IcalImportRefused('No has seleccionado ningún evento que se pueda importar.')
        missing = [
            event for event in selected
            if event.tipo_actividad_id is None and event.status != IcalImportEvent.STATUS_CREATED
        ]
        if missing:
            raise IcalImportRefused(
                f'{len(missing)} eventos seleccionados no tienen tipo de actividad. Elige uno en cada grupo.'
            )

        result = ApplyResult()
        already = imported_uids(academic_year, [event.uid for event in selected])
        for event in selected:
            if event.uid in already:
                event.status = IcalImportEvent.STATUS_DUPLICATE
                event.status_detail = ''
                event.save(update_fields=['status', 'status_detail'])
                result.skipped += 1
                continue
            try:
                with transaction.atomic():
                    activity = Actividad(
                        nombre=event.summary,
                        tipo_actividad=event.tipo_actividad,
                        academic_year=academic_year,
                        estado=Actividad.ESTADO_VISIBLE,
                        fecha_inicio=event.starts_at,
                        fecha_fin=event.ends_at,
                        descripcion=event.description or None,
                        evaluable=event.evaluable,
                        porcentaje_evaluacion=event.porcentaje_evaluacion,
                        ical_uid=event.uid,
                    )
                    # save() applies the normal automatic approval rule.
                    activity.save()
                    activity.asignaturas.set([subject])
                    LogActividad.objects.create(
                        object_type='actividad',
                        object_name=activity.nombre,
                        object_id=activity.id,
                        actividad=activity,
                        usuario=user,
                        tipo_log='Creation',
                        details=_log_details(ical_import, event),
                    )
            except IntegrityError:
                # A concurrent apply created the same UID first.
                event.status = IcalImportEvent.STATUS_DUPLICATE
                event.status_detail = ''
                event.save(update_fields=['status', 'status_detail'])
                result.skipped += 1
            else:
                event.status = IcalImportEvent.STATUS_CREATED
                event.status_detail = ''
                event.created_activity = activity
                event.save(update_fields=['status', 'status_detail', 'created_activity'])
                already.add(event.uid)
                result.created += 1

        if ical_import.moodle_course_id:
            MoodleCourseSubject.objects.update_or_create(
                moodle_course_id=ical_import.moodle_course_id,
                defaults={'subject': subject},
            )
        ical_import.state = IcalImport.STATE_APPLIED
        ical_import.applied_at = timezone.now()
        ical_import.save(update_fields=['state', 'applied_at'])
    return result


def mapped_subject(moodle_course_id):
    """Subject last used for this Moodle course, or None."""
    if not moodle_course_id:
        return None
    mapping = (
        MoodleCourseSubject.objects.filter(moodle_course_id=moodle_course_id)
        .select_related('subject')
        .first()
    )
    return mapping.subject if mapping else None
