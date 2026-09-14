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
from collections import defaultdict
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
    CatalogueImportPlanOverride,
    CatalogueImportRow,
    PlanCodeAlias,
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


MENTION_SEPARATOR = ' - '

PRIMARY = CatalogueImportRow.ROLE_PRIMARY
ALIAS = CatalogueImportRow.ROLE_ALIAS
MATCH_CODE = CatalogueImportRow.MATCH_CODE
MATCH_NAME = CatalogueImportRow.MATCH_NAME
MATCH_NEW = CatalogueImportRow.MATCH_NEW
MATCH_MANUAL = CatalogueImportRow.MATCH_MANUAL
FORCE_NEW = None


def plan_code_sort_key(code):
    return (0, int(code), code) if code.isdigit() else (1, 0, code)


def mention_parent(name):
    """Return the parent degree name of "<parent> - <mention>", or None."""
    if MENTION_SEPARATOR not in name:
        return None
    parent = name.rsplit(MENTION_SEPARATOR, 1)[0].strip()
    return parent or None


@dataclass
class PlanResolution:
    code: str
    name: str
    titulacion: Titulacion | None
    role: str
    status: str
    group: str
    group_name: str

    @property
    def is_mention(self):
        parent = mention_parent(self.name)
        return self.role == ALIAS and parent is not None and normalize_name(parent) == normalize_name(self.group_name)


class CatalogueMatcher:
    """Resolves plans and subjects against the current database state.

    Plan codes are resolved as a batch so that mentions ("<degree> - <mention>")
    and secondary codes sharing a degree name are grouped into one Titulacion,
    regardless of the order in which they appear in the file.
    """

    def __init__(self):
        self._subjects = {}
        self._claimed_subjects = set()
        self._uncoded_subjects = {}

    # -- plans -------------------------------------------------------------

    def resolve_plans(self, plans, overrides=None):
        """Resolve ``{plan_code: plan_name}`` into ``{plan_code: PlanResolution}``.

        ``overrides`` maps plan codes to a Titulacion (hard mapping) or to
        ``FORCE_NEW``. Overrides win over name and mention resolution but never
        over an exact code/alias match: registered codes are business keys.
        """
        codes = sorted(plans, key=plan_code_sort_key)
        overrides = {code: target for code, target in (overrides or {}).items() if code in plans}
        resolved = {}

        def existing(code, titulacion, role, status):
            resolved[code] = PlanResolution(
                code, plans[code], titulacion, role, status, f't:{titulacion.pk}', titulacion.nombre
            )

        # (a) Primary code or registered alias code.
        by_code = {t.codigo_plan: t for t in Titulacion.objects.filter(codigo_plan__in=codes)}
        by_alias = {
            alias.code: alias.titulacion
            for alias in PlanCodeAlias.objects.filter(code__in=codes).select_related('titulacion')
        }
        primary_taken = set()
        for code in codes:
            if code in by_code:
                existing(code, by_code[code], PRIMARY, MATCH_CODE)
                primary_taken.add(by_code[code].pk)
            elif code in by_alias:
                existing(code, by_alias[code], ALIAS, MATCH_CODE)

        name_index = defaultdict(list)
        for titulacion in Titulacion.objects.all():
            name_index[normalize_name(titulacion.nombre)].append(titulacion)

        def unique_titulacion(name):
            candidates = name_index.get(normalize_name(name), [])
            return candidates[0] if len(candidates) == 1 else None

        forced_new = {code for code, target in overrides.items() if target is FORCE_NEW and code not in resolved}

        # Same-name siblings follow a manual mapping (e.g. a second code of the same degree).
        override_targets_by_name = defaultdict(set)
        for code, target in overrides.items():
            if target is not FORCE_NEW and code not in resolved:
                override_targets_by_name[normalize_name(plans[code])].add(target)

        # (b) Manual mapping, sibling of a manual mapping, or exact name of an
        # existing Titulacion; the lowest code takes a free primary slot.
        for code in codes:
            if code in resolved or code in forced_new:
                continue
            titulacion, status = None, MATCH_NAME
            sibling_targets = override_targets_by_name.get(normalize_name(plans[code]), set())
            if overrides.get(code) is not None:
                titulacion, status = overrides[code], MATCH_MANUAL
            elif len(sibling_targets) == 1:
                titulacion = next(iter(sibling_targets))
            else:
                titulacion = unique_titulacion(plans[code])
            if titulacion is None:
                continue
            if not titulacion.codigo_plan and titulacion.pk not in primary_taken:
                primary_taken.add(titulacion.pk)
                existing(code, titulacion, PRIMARY, status)
            else:
                existing(code, titulacion, ALIAS, status)

        # Remaining codes grouped by exact normalized name within the file.
        pending = defaultdict(list)
        forced_pending = defaultdict(list)
        for code in codes:
            if code not in resolved:
                target = forced_pending if code in forced_new else pending
                target[normalize_name(plans[code])].append(code)

        def resolve_group_as_new(group_codes):
            primary = group_codes[0]
            for index, code in enumerate(group_codes):
                resolved[code] = PlanResolution(
                    code, plans[code], None, PRIMARY if index == 0 else ALIAS, MATCH_NEW,
                    f'new:{primary}', plans[primary],
                )

        def file_plan_named(name):
            wanted = normalize_name(name)
            matches = {resolved[code].group for code in resolved if normalize_name(plans[code]) == wanted}
            if len(matches) != 1:
                return None
            group = matches.pop()
            return next(resolved[code] for code in resolved if resolved[code].group == group)

        mention_groups = []
        for group_codes in forced_pending.values():
            resolve_group_as_new(group_codes)
            for code in group_codes:
                resolved[code].status = MATCH_MANUAL
        for group_codes in pending.values():
            if mention_parent(plans[group_codes[0]]) is None:
                resolve_group_as_new(group_codes)
            else:
                mention_groups.append(group_codes)

        # (c) Mentions, shortest names first so nested parents resolve before children.
        for group_codes in sorted(mention_groups, key=lambda group: len(plans[group[0]])):
            parent = mention_parent(plans[group_codes[0]])
            anchor = file_plan_named(parent)
            if anchor is None and not any(normalize_name(plans[code]) == normalize_name(parent) for code in plans):
                titulacion = unique_titulacion(parent)
                if titulacion is not None:
                    for code in group_codes:
                        existing(code, titulacion, ALIAS, MATCH_NAME)
                    continue
            if anchor is None:
                # (d) Unresolvable or ambiguous parent: a degree of its own.
                resolve_group_as_new(group_codes)
                continue
            status = MATCH_NEW if anchor.titulacion is None else MATCH_NAME
            for code in group_codes:
                resolved[code] = PlanResolution(
                    code, plans[code], anchor.titulacion, ALIAS, status, anchor.group, anchor.group_name
                )

        return resolved

    # -- subjects ----------------------------------------------------------

    def match_subject(self, titulacion, subject_code, subject_name):
        if titulacion is None:
            return None, MATCH_NEW
        key = (titulacion.pk, subject_code)
        if key in self._subjects:
            return self._subjects[key]

        asignatura = Asignatura.objects.filter(titulacion=titulacion, codigo_asignatura=subject_code).first()
        result = (asignatura, MATCH_CODE) if asignatura else (None, MATCH_NEW)
        if asignatura is None:
            candidate = self._unique_by_name(self._uncoded_subject_list(titulacion), subject_name)
            if candidate is not None and candidate.pk not in self._claimed_subjects:
                self._claimed_subjects.add(candidate.pk)
                result = (candidate, MATCH_NAME)

        self._subjects[key] = result
        return result

    @staticmethod
    def row_status(plan, subject_status, asignatura):
        if asignatura is None:
            return MATCH_NEW
        if plan.status == MATCH_MANUAL:
            return MATCH_MANUAL
        if MATCH_NAME in (plan.status, subject_status):
            return MATCH_NAME
        return MATCH_CODE

    @staticmethod
    def _unique_by_name(candidates, name):
        wanted = normalize_name(name)
        matches = [item for item in candidates if normalize_name(item.nombre) == wanted]
        return matches[0] if len(matches) == 1 else None

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


@dataclass
class SubjectConflict:
    group: str
    subject_code: str
    plan_codes: list
    fields: list

    def __str__(self):
        return (
            f'La asignatura {self.subject_code} aparece en los planes {", ".join(self.plan_codes)} '
            f'con distinto {", ".join(self.fields)}.'
        )


CONFLICT_FIELDS = (
    ('subject_name', 'nombre', lambda row: normalize_name(row.subject_name)),
    ('curricular_year', 'curso', lambda row: row.curricular_year),
    ('semester', 'semestre', lambda row: row.semester),
)


def find_subject_conflicts(rows, group_of=lambda row: row.plan_group):
    """Rows of grouped plan codes sharing a subject code must describe one subject."""
    by_subject = defaultdict(list)
    for row in rows:
        by_subject[(group_of(row), row.subject_code)].append(row)
    conflicts = []
    for (group, subject_code), subject_rows in by_subject.items():
        if len(subject_rows) < 2:
            continue
        fields = [label for _, label, value in CONFLICT_FIELDS if len({value(row) for row in subject_rows}) > 1]
        if fields:
            plan_codes = sorted({row.plan_code for row in subject_rows}, key=plan_code_sort_key)
            conflicts.append(SubjectConflict(group, subject_code, plan_codes, fields))
    return sorted(conflicts, key=lambda c: (c.group, plan_code_sort_key(c.subject_code)))


def _fill_from_grouped_duplicates(staged):
    """Copy curricular year/semester between grouped duplicates when unambiguous."""
    by_subject = defaultdict(list)
    for row in staged:
        by_subject[(row.plan_group, row.subject_code)].append(row)
    for subject_rows in by_subject.values():
        if len(subject_rows) < 2:
            continue
        for field in ('curricular_year', 'semester'):
            values = {getattr(row, field) for row in subject_rows} - {None}
            if len(values) == 1:
                value = values.pop()
                for row in subject_rows:
                    setattr(row, field, value)


def _plans_of(rows):
    return {row.plan_code: row.plan_name for row in rows}


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
    staged = [
        CatalogueImportRow(
            catalogue_import=catalogue_import,
            line_number=row.line_number,
            plan_code=row.plan_code,
            plan_name=row.plan_name,
            subject_code=row.subject_code,
            subject_name=row.subject_name,
            credits=row.credits,
            curricular_year=row.curricular_year,
            semester=row.semester,
        )
        for row in rows
    ]
    _assign_matches(staged, {})
    CatalogueImportRow.objects.bulk_create(staged)
    return catalogue_import


MATCH_FIELDS = [
    'target_titulacion', 'target_asignatura', 'match_status', 'plan_match_status', 'plan_role', 'plan_group',
    'curricular_year', 'semester',
]


def _assign_matches(rows, overrides):
    """Resolve plans and subjects onto row objects.

    Curricular year/semester already set (from the file or edited by an
    admin) are kept; missing values are prefilled from the matched subject
    and then shared between grouped duplicates.
    """
    matcher = CatalogueMatcher()
    plans = matcher.resolve_plans(_plans_of(rows), overrides)
    for row in rows:
        plan = plans[row.plan_code]
        asignatura, subject_status = matcher.match_subject(plan.titulacion, row.subject_code, row.subject_name)
        if asignatura is not None:
            if row.curricular_year is None and is_valid_curricular_year(asignatura.curso):
                row.curricular_year = asignatura.curso
            if row.semester is None and is_valid_semester(asignatura.semestre):
                row.semester = asignatura.semestre
        row.target_titulacion = plan.titulacion
        row.target_asignatura = asignatura
        row.match_status = matcher.row_status(plan, subject_status, asignatura)
        row.plan_match_status = plan.status
        row.plan_role = plan.role
        row.plan_group = plan.group
    _fill_from_grouped_duplicates(rows)
    return plans


def load_overrides(catalogue_import):
    return {
        override.plan_code: override.titulacion
        for override in catalogue_import.plan_overrides.select_related('titulacion')
    }


def refresh_draft_matching(catalogue_import):
    """Re-run plan and subject matching for a draft, honouring overrides."""
    rows = list(catalogue_import.rows.all())
    plans = _assign_matches(rows, load_overrides(catalogue_import))
    CatalogueImportRow.objects.bulk_update(rows, MATCH_FIELDS)
    return plans


OVERRIDE_AUTO = 'auto'
OVERRIDE_NEW = 'new'
OVERRIDE_TITULACION = 'titulacion'


@transaction.atomic
def set_plan_override(catalogue_import, plan_code, mode, titulacion=None):
    """Set (or clear, with ``OVERRIDE_AUTO``) the manual mapping of one plan code."""
    catalogue_import = CatalogueImport.objects.select_for_update().get(pk=catalogue_import.pk)
    if catalogue_import.state != CatalogueImport.STATE_DRAFT:
        raise ValidationError('Solo se pueden modificar importaciones en borrador.')
    plans = _plans_of(catalogue_import.rows.only('plan_code', 'plan_name'))
    if plan_code not in plans:
        raise ValidationError(f'El plan {plan_code} no forma parte de esta importación.')
    if mode not in (OVERRIDE_AUTO, OVERRIDE_NEW, OVERRIDE_TITULACION):
        raise ValidationError('Opción de asociación no válida.')
    if mode == OVERRIDE_TITULACION and titulacion is None:
        raise ValidationError('Elija una titulación.')

    automatic = CatalogueMatcher().resolve_plans(plans)
    if automatic[plan_code].status == MATCH_CODE:
        raise ValidationError(
            f'El código de plan {plan_code} ya está registrado en «{automatic[plan_code].group_name}». '
            'Los códigos se modifican en la administración de Django.'
        )

    overrides = load_overrides(catalogue_import)
    overrides.pop(plan_code, None)
    if mode == OVERRIDE_NEW:
        overrides[plan_code] = FORCE_NEW
    elif mode == OVERRIDE_TITULACION:
        overrides[plan_code] = titulacion

    resolution = CatalogueMatcher().resolve_plans(plans, overrides)[plan_code]
    if resolution.titulacion is not None:
        check_plan_code_assignment(resolution.titulacion, plan_code, resolution.role)

    CatalogueImportPlanOverride.objects.filter(catalogue_import=catalogue_import, plan_code=plan_code).delete()
    if mode != OVERRIDE_AUTO:
        CatalogueImportPlanOverride.objects.create(
            catalogue_import=catalogue_import,
            plan_code=plan_code,
            titulacion=titulacion if mode == OVERRIDE_TITULACION else None,
        )
    refresh_draft_matching(catalogue_import)
    return resolution


def check_plan_code_assignment(titulacion, code, role):
    """Raise ValidationError if ``code`` cannot be recorded on ``titulacion`` with ``role``."""
    if role == PRIMARY and titulacion.codigo_plan and titulacion.codigo_plan != code:
        raise ValidationError(
            f'La titulación «{titulacion}» ya tiene el código de plan {titulacion.codigo_plan}; '
            f'no se sustituye por {code}.'
        )
    if titulacion.codigo_plan == code:
        return
    owner = Titulacion.objects.filter(codigo_plan=code).exclude(pk=titulacion.pk).first()
    if owner is not None:
        raise ValidationError(f'El código de plan {code} ya es el código principal de «{owner}».')
    alias = PlanCodeAlias.objects.filter(code=code).select_related('titulacion').first()
    if alias is not None and alias.titulacion_id != titulacion.pk:
        raise ValidationError(
            f'El código de plan {code} ya es un alias de «{alias.titulacion}»; no se reasigna a «{titulacion}».'
        )


def register_plan_code(titulacion, code, name, role):
    """Record ``code`` on ``titulacion`` as its primary code or as an alias."""
    check_plan_code_assignment(titulacion, code, role)
    if titulacion.codigo_plan == code:
        return
    if role == PRIMARY:
        titulacion.codigo_plan = code
        titulacion.save(update_fields=['codigo_plan'])
    else:
        PlanCodeAlias.objects.get_or_create(code=code, defaults={'titulacion': titulacion, 'name': name})


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

    rows = list(catalogue_import.rows.all())
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

    # Matches are re-resolved (with manual overrides): the database may have changed since the draft.
    matcher = CatalogueMatcher()
    plans = matcher.resolve_plans(_plans_of(rows), load_overrides(catalogue_import))
    conflicts = find_subject_conflicts(rows, group_of=lambda row: plans[row.plan_code].group)
    if conflicts:
        raise ValidationError([str(conflict) for conflict in conflicts])

    # Primary codes first so each group's Titulacion exists before its aliases.
    titulaciones = {}
    for plan in sorted(plans.values(), key=lambda p: (p.role != PRIMARY, plan_code_sort_key(p.code))):
        titulacion = plan.titulacion or titulaciones.get(plan.group)
        if titulacion is None:
            titulacion = Titulacion.objects.create(nombre=plan.group_name, codigo_plan=plan.code)
        titulaciones[plan.group] = titulacion
        register_plan_code(titulacion, plan.code, plan.name, plan.role)

    rows.sort(key=lambda row: (plans[row.plan_code].role != PRIMARY, plan_code_sort_key(row.plan_code), row.subject_code))
    for row in rows:
        plan = plans[row.plan_code]
        titulacion = titulaciones[plan.group]
        asignatura, subject_status = matcher.match_subject(plan.titulacion, row.subject_code, row.subject_name)
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
        row.match_status = matcher.row_status(plan, subject_status, asignatura)
        row.plan_match_status = plan.status
        row.plan_role = plan.role
        row.plan_group = f't:{titulacion.pk}'
        row.save(update_fields=[
            'target_titulacion', 'target_asignatura', 'match_status', 'plan_match_status', 'plan_role', 'plan_group',
        ])

    catalogue_import.state = CatalogueImport.STATE_APPLIED
    catalogue_import.applied_at = timezone.now()
    catalogue_import.save(update_fields=['state', 'applied_at'])
    return catalogue_import
