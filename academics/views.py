from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from users.views import is_admin

from .catalogue_import import (
    CURRICULAR_YEAR_ALLOWED_TEXT,
    CURRICULAR_YEAR_CHOICES,
    CURRICULAR_YEAR_VALUES,
    SEMESTER_ALLOWED_TEXT,
    SEMESTER_CHOICES,
    SEMESTER_VALUES,
    apply_import,
    build_draft,
    parse_catalogue,
)
from .forms import CatalogueUploadForm
from .models import AcademicYear, CatalogueImport, CatalogueImportRow


def admin_required(view):
    return login_required(user_passes_test(is_admin)(view))


def _validation_messages(error):
    return error.messages if hasattr(error, 'messages') else [str(error)]


@admin_required
def catalogue_import_list(request):
    parse_errors = []
    if request.method == 'POST':
        form = CatalogueUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data['file']
            rows, parse_errors = parse_catalogue(upload.read())
            if not parse_errors and not rows:
                form.add_error('file', 'El fichero no contiene asignaturas.')
            elif not parse_errors:
                try:
                    with transaction.atomic():
                        year = form.cleaned_data['academic_year']
                        if year is None:
                            year = AcademicYear(
                                code=form.cleaned_data['new_year_code'],
                                starts_on=form.cleaned_data['new_year_starts_on'],
                                ends_on=form.cleaned_data['new_year_ends_on'],
                            )
                            year.full_clean()
                            year.save()
                        draft = build_draft(year, rows, upload.name, request.user)
                except ValidationError as error:
                    for message in _validation_messages(error):
                        form.add_error(None, message)
                else:
                    messages.success(request, f'Borrador creado con {len(rows)} asignaturas. Revíselo antes de aplicarlo.')
                    return redirect('catalogue_import_detail', pk=draft.pk)
    else:
        form = CatalogueUploadForm()

    imports = (
        CatalogueImport.objects.select_related('academic_year', 'created_by')
        .annotate(
            row_count=Count('rows'),
            incomplete_count=Count('rows', filter=Q(rows__curricular_year__isnull=True) | Q(rows__semester__isnull=True)),
        )
    )
    return render(request, 'academics/catalogue_import_list.html', {
        'form': form,
        'parse_errors': parse_errors,
        'imports': imports,
        'years': AcademicYear.objects.annotate(offering_count=Count('offerings')),
    })


def _parse_allowed_int(raw, allowed):
    raw = (raw or '').strip()
    if raw == '':
        return None, True
    try:
        value = int(raw)
    except ValueError:
        return None, False
    return value, value in allowed


def _save_row_metadata(request, catalogue_import):
    rows = {row.pk: row for row in catalogue_import.rows.all()}
    changed, invalid = [], []
    for row_id, row in rows.items():
        year_field, semester_field = f'curricular_year_{row_id}', f'semester_{row_id}'
        if year_field not in request.POST and semester_field not in request.POST:
            continue
        curricular_year, year_ok = _parse_allowed_int(request.POST.get(year_field), CURRICULAR_YEAR_VALUES)
        semester, semester_ok = _parse_allowed_int(request.POST.get(semester_field), SEMESTER_VALUES)
        if not (year_ok and semester_ok):
            invalid.append(row)
            continue
        if year_field in request.POST:
            row.curricular_year = curricular_year
        if semester_field in request.POST:
            row.semester = semester
        changed.append(row)
    if invalid:
        codes = ', '.join(f'{row.plan_code}/{row.subject_code}' for row in invalid[:10])
        messages.error(
            request,
            f'Valores no válidos en: {codes}. Curso: {CURRICULAR_YEAR_ALLOWED_TEXT}; '
            f'semestre: {SEMESTER_ALLOWED_TEXT}. No se ha guardado nada.',
        )
        return
    CatalogueImportRow.objects.bulk_update(changed, ['curricular_year', 'semester'])
    messages.success(request, f'Cambios guardados en {len(changed)} asignaturas.')


@admin_required
def catalogue_import_detail(request, pk):
    catalogue_import = get_object_or_404(CatalogueImport.objects.select_related('academic_year'), pk=pk)
    only_incomplete = request.GET.get('incomplete') == '1'

    if request.method == 'POST':
        if catalogue_import.state != CatalogueImport.STATE_DRAFT:
            messages.error(request, 'Solo se pueden editar importaciones en borrador.')
        else:
            _save_row_metadata(request, catalogue_import)
        target = request.path + ('?incomplete=1' if request.POST.get('incomplete') == '1' else '')
        return redirect(target)

    all_rows = catalogue_import.rows.all()
    summary = all_rows.aggregate(
        total=Count('id'),
        by_code=Count('id', filter=Q(match_status=CatalogueImportRow.MATCH_CODE)),
        by_name=Count('id', filter=Q(match_status=CatalogueImportRow.MATCH_NAME)),
        new=Count('id', filter=Q(match_status=CatalogueImportRow.MATCH_NEW)),
        incomplete=Count('id', filter=Q(curricular_year__isnull=True) | Q(semester__isnull=True)),
    )
    rows = catalogue_import.incomplete_rows() if only_incomplete else all_rows
    rows = rows.select_related('target_titulacion', 'target_asignatura').order_by('plan_code', 'curricular_year', 'semester', 'subject_code')

    plans = []
    for row in rows:
        if not plans or plans[-1]['plan_code'] != row.plan_code:
            titulacion = row.target_titulacion
            if titulacion is None:
                plan_status = CatalogueImportRow.MATCH_NEW
            elif titulacion.codigo_plan == row.plan_code:
                plan_status = CatalogueImportRow.MATCH_CODE
            else:
                plan_status = CatalogueImportRow.MATCH_NAME
            plans.append({
                'plan_code': row.plan_code,
                'plan_name': row.plan_name,
                'titulacion': titulacion,
                'status': plan_status,
                'rows': [],
            })
        plans[-1]['rows'].append(row)

    return render(request, 'academics/catalogue_import_detail.html', {
        'catalogue_import': catalogue_import,
        'is_draft': catalogue_import.state == CatalogueImport.STATE_DRAFT,
        'summary': summary,
        'plans': plans,
        'only_incomplete': only_incomplete,
        'curricular_year_choices': CURRICULAR_YEAR_CHOICES,
        'semester_choices': SEMESTER_CHOICES,
        'can_apply': (
            catalogue_import.state == CatalogueImport.STATE_DRAFT
            and summary['total'] > 0
            and summary['incomplete'] == 0
            and catalogue_import.academic_year.state != AcademicYear.STATE_ARCHIVED
        ),
    })


@admin_required
@require_POST
def catalogue_import_apply(request, pk):
    catalogue_import = get_object_or_404(CatalogueImport, pk=pk)
    try:
        apply_import(catalogue_import)
    except ValidationError as error:
        for message in _validation_messages(error):
            messages.error(request, message)
    else:
        messages.success(
            request,
            f'Importación aplicada al curso {catalogue_import.academic_year}. '
            'El curso no se activa automáticamente.',
        )
    return redirect('catalogue_import_detail', pk=pk)


@admin_required
@require_POST
def catalogue_import_delete(request, pk):
    catalogue_import = get_object_or_404(CatalogueImport, pk=pk)
    if catalogue_import.state != CatalogueImport.STATE_DRAFT:
        messages.error(request, 'Solo se pueden eliminar importaciones en borrador.')
        return redirect('catalogue_import_detail', pk=pk)
    catalogue_import.delete()
    messages.success(request, 'Borrador eliminado.')
    return redirect('catalogue_import_list')


@admin_required
@require_POST
def academic_year_activate(request, pk):
    year = get_object_or_404(AcademicYear, pk=pk)
    next_url = request.POST.get('next')
    try:
        with transaction.atomic():
            year.activate()
    except ValidationError as error:
        for message in _validation_messages(error):
            messages.error(request, f'No se puede activar el curso {year}: {message}')
    except IntegrityError:
        messages.error(request, f'No se puede activar el curso {year}: ya hay otro curso activo.')
    else:
        messages.success(request, f'Curso {year} activado.')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('catalogue_import_list')
