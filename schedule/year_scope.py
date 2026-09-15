"""Academic-year scoping for activity views.

* Year selection: dashboards let staff browse one or more non-draft years through
  the ``academic_year`` GET parameter; the default is the active year only.
* Read-only guard: activities outside the active year cannot be modified. Every
  mutating view calls :func:`read_only_response` before touching the activity.
"""
from django.http import JsonResponse
from django.shortcuts import render

from academics.models import AcademicYear

YEAR_PARAM = 'academic_year'

READ_ONLY_MESSAGE = (
    'La actividad "%(name)s" pertenece al curso %(year)s, que no es el curso activo. '
    'Las actividades de cursos anteriores son de solo lectura.'
)


def parse_year_selection(request):
    """Return ``(selectable_years, selected_years)`` for the request.

    Unknown or draft year ids are ignored. When nothing valid is selected the
    active year is selected (or nothing when no year is active).
    """
    selectable = list(AcademicYear.selectable())
    by_id = {str(year.pk): year for year in selectable}
    selected = [by_id[raw] for raw in dict.fromkeys(request.GET.getlist(YEAR_PARAM)) if raw in by_id]
    if not selected:
        selected = [year for year in selectable if year.is_active]
    return selectable, selected


def year_selection_context(request):
    selectable, selected = parse_year_selection(request)
    selected_ids = [year.pk for year in selected]
    active = next((year for year in selectable if year.is_active), None)
    return {
        'academic_years': selectable,
        'selected_academic_years': selected,
        'selected_academic_year_ids': selected_ids,
        'selected_academic_year_id_strings': [str(pk) for pk in selected_ids],
        'active_academic_year': active,
        'past_years_selected': any(not year.is_active for year in selected),
    }


def read_only_message(activity):
    return READ_ONLY_MESSAGE % {'name': activity.nombre, 'year': activity.academic_year.code}


def read_only_response(request, activity, as_json=False):
    """Return a 403 response when ``activity`` is read-only, otherwise None."""
    if not activity.is_read_only:
        return None
    message = read_only_message(activity)
    if as_json:
        return JsonResponse({'success': False, 'error': message}, status=403)
    return render(
        request,
        'schedule/activity_read_only.html',
        {'activity': activity, 'message': message},
        status=403,
    )
