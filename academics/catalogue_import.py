"""Catalogue import domain service.

Turns an official catalogue CSV export into a staged draft import, matches it
against existing plans (Titulacion) and subjects (Asignatura), and applies it
to an academic year. Teachers and any personal data in the source file are
never read into the model.
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AcademicYear,
    Asignatura,
    CatalogueImport,
    CatalogueImportRow,
    SubjectOffering,
    Titulacion,
)

# Code domain shared with the rest of the app (see schedule/views.py and
# users/views.py): curso 10 = elective ("Optativa"), 1000 = final project
# ("TFE"); semestre 3 = elective/annual.
CURRICULAR_YEAR_CHOICES = (
    (1, '1º'),
    (2, '2º'),
    (3, '3º'),
    (4, '4º'),
    (5, '5º'),
    (6, '6º'),
    (10, 'Optativa'),
    (1000, 'TFE'),
)
SEMESTER_CHOICES = (
    (1, 'Primer semestre'),
    (2, 'Segundo semestre'),
    (3, 'Optativa/Anual'),
)
CURRICULAR_YEAR_VALUES = frozenset(value for value, _ in CURRICULAR_YEAR_CHOICES)
SEMESTER_VALUES = frozenset(value for value, _ in SEMESTER_CHOICES)
CURRICULAR_YEAR_ALLOWED_TEXT = '1-6, 10 (optativa) o 1000 (TFE)'
SEMESTER_ALLOWED_TEXT = '1 (primer semestre), 2 (segundo semestre) o 3 (optativa/anual)'

REQUIRED_FIELDS = ('plan_code', 'plan_name', 'subject_code', 'subject_name')

# Canonical field -> accepted header spellings. The official export column
# "Curso" is the ACADEMIC year (e.g. "2024-25") and is deliberately absent.
HEADER_ALIASES = {
    'plan_code': ('plan_code', 'codPlan'),
    'plan_name': ('plan_name', 'Plan de estudios'),
    'subject_code': ('subject_code', 'codAsignatura'),
    'subject_name': ('subject_name', 'Asignatura'),
    'credits': ('credits', 'Créditos de la asignatura'),
    'curricular_year': ('curricular_year', 'curso_plan'),
    'semester': ('semester', 'Semestre'),
}


@dataclass
class ParsedRow:
    line_number: int
    plan_code: str
    plan_name: str
    subject_code: str
    subject_name: str
    credits: Decimal | None = None
    curricular_year: int | None = None
    semester: int | None = None

    @property
    def key(self):
        return (self.plan_code, self.subject_code)


@dataclass
class ParseError:
    line_number: int
    message: str

    def __str__(self):
        return f'Línea {self.line_number}: {self.message}'


def normalize_name(value):
    """Accent-, case-, whitespace- and punctuation-insensitive comparison key."""
    decomposed = unicodedata.normalize('NFKD', value or '')
    without_accents = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    alphanumeric = re.sub(r'[\W_]+', ' ', without_accents.casefold())
    return ' '.join(alphanumeric.split())


def _header_key(value):
    return normalize_name(value.lstrip('﻿'))


_ALIAS_LOOKUP = {
    _header_key(alias): field
    for field, aliases in HEADER_ALIASES.items()
    for alias in aliases
}


def _read_text(source):
    if hasattr(source, 'read'):
        source = source.read()
    if isinstance(source, (bytes, bytearray)):
        source = bytes(source).decode('utf-8-sig')
    return source.lstrip('﻿')


def _detect_delimiter(text):
    first_line = text.split('\n', 1)[0]
    return ';' if first_line.count(';') >= first_line.count(',') else ','


def _parse_int(raw, label, allowed, allowed_text, line_number, errors):
    if raw == '':
        return None
    try:
        value = int(raw)
    except ValueError:
        errors.append(ParseError(line_number, f'{label} «{raw}» no es un número entero.'))
        return None
    if value not in allowed:
        errors.append(ParseError(line_number, f'{label} {value} no válido; valores permitidos: {allowed_text}.'))
        return None
    return value


def _parse_credits(raw, line_number, errors):
    if raw == '':
        return None
    try:
        value = Decimal(raw.replace(',', '.'))
    except InvalidOperation:
        value = None
    # Must fit CatalogueImportRow.credits (max_digits=5, decimal_places=2).
    if value is None or not value.is_finite() or value < 0 or value >= 1000 or value != value.quantize(Decimal('0.01')):
        errors.append(ParseError(line_number, f'Créditos «{raw}» no es un número válido.'))
        return None
    return value


def parse_catalogue(source):
    """Parse a catalogue CSV.

    ``source`` may be text, bytes or a file-like object returning either.
    Returns ``(rows, errors)`` where rows are deduplicated ``ParsedRow``
    instances and errors are ``ParseError`` instances with line numbers.
    """
    try:
        text = _read_text(source)
    except UnicodeDecodeError:
        return [], [ParseError(1, 'El fichero no está codificado en UTF-8.')]

    if not text.strip():
        return [], [ParseError(1, 'El fichero está vacío.')]

    reader = csv.reader(io.StringIO(text, newline=''), delimiter=_detect_delimiter(text))
    header = next(reader, [])
    columns = {}
    for index, name in enumerate(header):
        field = _ALIAS_LOOKUP.get(_header_key(name))
        if field and field not in columns:
            columns[field] = index

    missing = [field for field in REQUIRED_FIELDS if field not in columns]
    if missing:
        expected = ', '.join(' | '.join(HEADER_ALIASES[field]) for field in missing)
        return [], [ParseError(1, f'Faltan columnas obligatorias: {expected}.')]

    rows = {}
    errors = []
    for record in reader:
        line_number = reader.line_num
        if not any(cell.strip() for cell in record):
            continue

        def cell(field):
            index = columns.get(field)
            if index is None or index >= len(record):
                return ''
            return record[index].strip()

        values = {field: cell(field) for field in REQUIRED_FIELDS}
        missing_values = [field for field, value in values.items() if not value]
        if missing_values:
            errors.append(ParseError(line_number, f'Faltan valores obligatorios: {", ".join(missing_values)}.'))
            continue

        row_errors = []
        row = ParsedRow(
            line_number=line_number,
            plan_code=values['plan_code'],
            plan_name=' '.join(values['plan_name'].split()),
            subject_code=values['subject_code'],
            subject_name=' '.join(values['subject_name'].split()),
            credits=_parse_credits(cell('credits'), line_number, row_errors),
            curricular_year=_parse_int(cell('curricular_year'), 'Curso del plan', CURRICULAR_YEAR_VALUES, CURRICULAR_YEAR_ALLOWED_TEXT, line_number, row_errors),
            semester=_parse_int(cell('semester'), 'Semestre', SEMESTER_VALUES, SEMESTER_ALLOWED_TEXT, line_number, row_errors),
        )
        if row_errors:
            errors.extend(row_errors)
            continue

        previous = rows.get(row.key)
        if previous is None:
            rows[row.key] = row
            continue
        _merge_duplicate(previous, row, errors)

    return list(rows.values()), errors


def _merge_duplicate(previous, row, errors):
    """The official export repeats a subject once per teacher; merge repeats."""
    if previous.plan_name != row.plan_name:
        errors.append(ParseError(
            row.line_number,
            f'El plan {row.plan_code} tiene un nombre distinto al de la línea {previous.line_number}.',
        ))
    if previous.subject_name != row.subject_name:
        errors.append(ParseError(
            row.line_number,
            f'La asignatura {row.subject_code} tiene un nombre distinto al de la línea {previous.line_number}.',
        ))
    for field, label in (('curricular_year', 'curso del plan'), ('semester', 'semestre'), ('credits', 'créditos')):
        old, new = getattr(previous, field), getattr(row, field)
        if new is None:
            continue
        if old is None:
            setattr(previous, field, new)
        elif old != new:
            errors.append(ParseError(
                row.line_number,
                f'La asignatura {row.subject_code} tiene un {label} distinto al de la línea {previous.line_number}.',
            ))


class CatalogueMatcher:
    """Resolves plans and subjects against the current database state.

    A Titulacion (or Asignatura) can be claimed by name only once per run, so
    two plan codes sharing a name never collapse onto the same record.
    """

    def __init__(self):
        self._plans = {}
        self._subjects = {}
        self._claimed_plans = set()
        self._claimed_subjects = set()
        self._uncoded_plans = None
        self._uncoded_subjects = {}

    def match_plan(self, plan_code, plan_name):
        if plan_code in self._plans:
            return self._plans[plan_code]

        titulacion = Titulacion.objects.filter(codigo_plan=plan_code).first()
        result = (titulacion, CatalogueImportRow.MATCH_CODE) if titulacion else (None, CatalogueImportRow.MATCH_NEW)
        if titulacion is None:
            candidate = self._unique_by_name(self._uncoded_plan_list(), plan_name, lambda t: t.nombre)
            if candidate is not None and candidate.pk not in self._claimed_plans:
                self._claimed_plans.add(candidate.pk)
                result = (candidate, CatalogueImportRow.MATCH_NAME)

        self._plans[plan_code] = result
        return result

    def match_subject(self, titulacion, subject_code, subject_name):
        if titulacion is None:
            return None, CatalogueImportRow.MATCH_NEW
        key = (titulacion.pk, subject_code)
        if key in self._subjects:
            return self._subjects[key]

        asignatura = Asignatura.objects.filter(titulacion=titulacion, codigo_asignatura=subject_code).first()
        result = (asignatura, CatalogueImportRow.MATCH_CODE) if asignatura else (None, CatalogueImportRow.MATCH_NEW)
        if asignatura is None:
            candidate = self._unique_by_name(self._uncoded_subject_list(titulacion), subject_name, lambda a: a.nombre)
            if candidate is not None and candidate.pk not in self._claimed_subjects:
                self._claimed_subjects.add(candidate.pk)
                result = (candidate, CatalogueImportRow.MATCH_NAME)

        self._subjects[key] = result
        return result

    def match(self, plan_code, plan_name, subject_code, subject_name):
        """Return (titulacion, asignatura, row match status)."""
        titulacion, plan_status = self.match_plan(plan_code, plan_name)
        asignatura, subject_status = self.match_subject(titulacion, subject_code, subject_name)
        if asignatura is None:
            status = CatalogueImportRow.MATCH_NEW
        elif CatalogueImportRow.MATCH_NAME in (plan_status, subject_status):
            status = CatalogueImportRow.MATCH_NAME
        else:
            status = CatalogueImportRow.MATCH_CODE
        return titulacion, asignatura, status

    @staticmethod
    def _unique_by_name(candidates, name, get_name):
        wanted = normalize_name(name)
        matches = [item for item in candidates if normalize_name(get_name(item)) == wanted]
        return matches[0] if len(matches) == 1 else None

    def _uncoded_plan_list(self):
        if self._uncoded_plans is None:
            self._uncoded_plans = list(
                Titulacion.objects.filter(Q(codigo_plan__isnull=True) | Q(codigo_plan=''))
            )
        return self._uncoded_plans

    def _uncoded_subject_list(self, titulacion):
        if titulacion.pk not in self._uncoded_subjects:
            self._uncoded_subjects[titulacion.pk] = list(
                Asignatura.objects.filter(titulacion=titulacion).filter(
                    Q(codigo_asignatura__isnull=True) | Q(codigo_asignatura='')
                )
            )
        return self._uncoded_subjects[titulacion.pk]


def is_valid_curricular_year(value):
    return value in CURRICULAR_YEAR_VALUES


def is_valid_semester(value):
    return value in SEMESTER_VALUES


@transaction.atomic
def build_draft(academic_year, rows, filename, user):
    """Store parsed rows as a draft import with matching results."""
    if academic_year.state == AcademicYear.STATE_ARCHIVED:
        raise ValidationError('No se puede importar un catálogo en un curso archivado.')

    catalogue_import = CatalogueImport.objects.create(
        academic_year=academic_year,
        source_filename=filename or '',
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    matcher = CatalogueMatcher()
    staged = []
    for row in rows:
        titulacion, asignatura, status = matcher.match(
            row.plan_code, row.plan_name, row.subject_code, row.subject_name
        )
        curricular_year = row.curricular_year
        semester = row.semester
        if asignatura is not None:
            if curricular_year is None and is_valid_curricular_year(asignatura.curso):
                curricular_year = asignatura.curso
            if semester is None and is_valid_semester(asignatura.semestre):
                semester = asignatura.semestre
        staged.append(CatalogueImportRow(
            catalogue_import=catalogue_import,
            line_number=row.line_number,
            plan_code=row.plan_code,
            plan_name=row.plan_name,
            subject_code=row.subject_code,
            subject_name=row.subject_name,
            credits=row.credits,
            curricular_year=curricular_year,
            semester=semester,
            target_titulacion=titulacion,
            target_asignatura=asignatura,
            match_status=status,
        ))
    CatalogueImportRow.objects.bulk_create(staged)
    return catalogue_import


@transaction.atomic
def apply_import(catalogue_import):
    """Create/update plans, subjects and offerings from a complete draft import."""
    catalogue_import = (
        CatalogueImport.objects.select_for_update()
        .select_related('academic_year')
        .get(pk=catalogue_import.pk)
    )
    if catalogue_import.state != CatalogueImport.STATE_DRAFT:
        raise ValidationError('La importación ya se ha aplicado.')
    academic_year = catalogue_import.academic_year
    if academic_year.state == AcademicYear.STATE_ARCHIVED:
        raise ValidationError('No se puede aplicar una importación a un curso archivado.')

    rows = list(catalogue_import.rows.order_by('plan_code', 'subject_code'))
    if not rows:
        raise ValidationError('La importación no contiene asignaturas.')
    incomplete = [row for row in rows if not row.is_complete]
    if incomplete:
        raise ValidationError(
            f'{len(incomplete)} asignaturas no tienen curso del plan y semestre.'
        )
    invalid = [
        row for row in rows
        if not (is_valid_curricular_year(row.curricular_year) and is_valid_semester(row.semester))
    ]
    if invalid:
        raise ValidationError(f'{len(invalid)} asignaturas tienen curso del plan o semestre no válido.')

    matcher = CatalogueMatcher()
    created_plans = {}
    for row in rows:
        titulacion, asignatura, status = matcher.match(
            row.plan_code, row.plan_name, row.subject_code, row.subject_name
        )

        if titulacion is None:
            titulacion = created_plans.get(row.plan_code)
            if titulacion is None:
                titulacion = Titulacion.objects.create(nombre=row.plan_name, codigo_plan=row.plan_code)
                created_plans[row.plan_code] = titulacion
        elif not titulacion.codigo_plan:
            titulacion.codigo_plan = row.plan_code
            titulacion.save(update_fields=['codigo_plan'])

        if asignatura is None:
            asignatura = Asignatura.objects.filter(titulacion=titulacion, codigo_asignatura=row.subject_code).first()
        if asignatura is None:
            asignatura = Asignatura.objects.create(
                nombre=row.subject_name,
                codigo_asignatura=row.subject_code,
                titulacion=titulacion,
                curso=row.curricular_year,
                semestre=row.semester,
            )
        else:
            if not asignatura.codigo_asignatura:
                asignatura.codigo_asignatura = row.subject_code
            asignatura.curso = row.curricular_year
            asignatura.semestre = row.semester
            asignatura.save(update_fields=['codigo_asignatura', 'curso', 'semestre'])

        SubjectOffering.objects.update_or_create(
            academic_year=academic_year,
            subject=asignatura,
            defaults={
                'curricular_year': row.curricular_year,
                'semester': row.semester,
                'state': SubjectOffering.STATE_OFFERED,
            },
        )

        row.target_titulacion = titulacion
        row.target_asignatura = asignatura
        row.match_status = status
        row.save(update_fields=['target_titulacion', 'target_asignatura', 'match_status'])

    catalogue_import.state = CatalogueImport.STATE_APPLIED
    catalogue_import.applied_at = timezone.now()
    catalogue_import.save(update_fields=['state', 'applied_at'])
    return catalogue_import
