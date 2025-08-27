from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from users.views import is_teacher, is_coordinator
from .forms import ActividadForm, VistaCalendarioForm
from .models import Actividad, VistaCalendario
from icalendar import Calendar, Event
from django.http import HttpResponse, JsonResponse
from academics.models import Asignatura

@login_required
@user_passes_test(is_teacher)
def activity_form(request, pk=None):
    if pk:
        activity = get_object_or_404(Actividad, pk=pk)
        asignatura = activity.asignatura
    else:
        activity = None
        asignatura_id = request.GET.get('asignatura')
        if asignatura_id:
            asignatura = get_object_or_404(Asignatura, pk=asignatura_id)
        else:
            return redirect('teacher_dashboard')

    if request.method == 'POST':
        form = ActividadForm(request.POST, instance=activity)
        if form.is_valid():
            form.save()
            return redirect('teacher_dashboard')
    else:
        initial_data = {}
        if not pk:
            initial_data['asignatura'] = asignatura.id
        form = ActividadForm(instance=activity, initial=initial_data)

    return render(request, 'schedule/activity_form.html', {'form': form, 'asignatura': asignatura})

@login_required
@user_passes_test(is_teacher)
def activity_delete(request, pk):
    activity = get_object_or_404(Actividad, pk=pk)
    if request.method == 'POST':
        activity.delete()
        return redirect('teacher_dashboard')
    return render(request, 'schedule/activity_confirm_delete.html', {'activity': activity})

@login_required
@user_passes_test(is_teacher)
def activity_list(request):
    activities = Actividad.objects.all()
    return render(request, 'schedule/activity_list.html', {'activities': activities})

@login_required
def calendar_view_panel(request):
    calendar_views = VistaCalendario.objects.filter(usuario=request.user)
    return render(request, 'schedule/calendar_view_panel.html', {'calendar_views': calendar_views})

@login_required
def create_calendar_view(request):
    if request.method == 'POST':
        form = VistaCalendarioForm(request.POST)
        if form.is_valid():
            calendar_view = form.save(commit=False)
            calendar_view.usuario = request.user
            calendar_view.save()
            form.save_m2m() # Save ManyToMany relationships
            return redirect('calendar_view_panel')
    else:
        form = VistaCalendarioForm()
    return render(request, 'schedule/create_calendar_view.html', {'form': form})

@login_required
def delete_calendar_view(request, pk):
    calendar_view = get_object_or_404(VistaCalendario, pk=pk, usuario=request.user)
    if request.method == 'POST':
        calendar_view.delete()
        return redirect('calendar_view_panel')
    return render(request, 'schedule/calendar_view_confirm_delete.html', {'calendar_view': calendar_view})

def ical_feed(request, token):
    calendar_view = get_object_or_404(VistaCalendario, token=token)
    
    cal = Calendar()
    cal.add('prodid', '-//My Calendar App//mxm.dk//')
    cal.add('version', '2.0')

    activities = Actividad.objects.all()

    if calendar_view.asignaturas.exists():
        activities = activities.filter(asignatura__in=calendar_view.asignaturas.all())
    if calendar_view.tipos_actividad.exists():
        activities = activities.filter(tipo_actividad__in=calendar_view.tipos_actividad.all())

    for activity in activities:
        event = Event()
        event.add('summary', activity.nombre)
        event.add('dtstart', activity.fecha_inicio)
        event.add('dtend', activity.fecha_fin)
        event.add('description', activity.descripcion)
        cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="{}.ics"'.format(calendar_view.nombre)
    return response

@login_required
@user_passes_test(is_coordinator)
def delete_misassigned_activity(request, pk):
    activity = get_object_or_404(Actividad, pk=pk)
    if request.method == 'POST':
        activity.delete()
        return redirect('coordinator_dashboard')
    return render(request, 'schedule/activity_confirm_delete.html', {'activity': activity})

def get_cursos(request):
    titulacion_id = request.GET.get('titulacion_id')
    
    cursos_qs = Asignatura.objects.filter(titulacion_id=titulacion_id).order_by('curso').values_list('curso', flat=True).distinct()
    
    # Exclude TFE for non-coordinators
    if not is_coordinator(request.user):
        cursos_qs = cursos_qs.exclude(curso=1000)

    curso_map = {
        1: "Primer Curso",
        2: "Segundo Curso",
        3: "Tercer Curso",
        4: "Cuarto Curso",
        10: "Optativa",
        1000: "TFE"
    }
    
    cursos_display = [curso_map.get(c, c) for c in cursos_qs]
    
    return JsonResponse(cursos_display, safe=False)

def get_semestres(request):
    titulacion_id = request.GET.get('titulacion_id')
    curso_str = request.GET.get('curso')

    curso_map_inv = {
        "Primer Curso": 1,
        "Segundo Curso": 2,
        "Tercer Curso": 3,
        "Cuarto Curso": 4,
        "Optativa": 10,
        "TFE": 1000
    }
    curso = curso_map_inv.get(curso_str, curso_str)

    semestres = Asignatura.objects.filter(titulacion_id=titulacion_id, curso=curso).order_by('semestre').values_list('semestre', flat=True).distinct()
    
    semestre_map = {1: "Primer Semestre", 2: "Segundo Semestre", 3: "Optativa"}
    semestres_display = [semestre_map.get(s, s) for s in semestres]
    
    return JsonResponse(semestres_display, safe=False)

def get_asignaturas(request):
    titulacion_id = request.GET.get('titulacion_id')
    curso_str = request.GET.get('curso')
    semestre_str = request.GET.get('semestre')

    curso_map_inv = {
        "Primer Curso": 1,
        "Segundo Curso": 2,
        "Tercer Curso": 3,
        "Cuarto Curso": 4,
        "Optativa": 10,
        "TFE": 1000
    }
    curso = curso_map_inv.get(curso_str, curso_str)

    semestre_map_inv = {"Primer Semestre": 1, "Segundo Semestre": 2, "Optativa": 3}
    semestre = semestre_map_inv.get(semestre_str, semestre_str)

    asignaturas = Asignatura.objects.filter(
        titulacion_id=titulacion_id, 
        curso=curso, 
        semestre=semestre
    )
    
    if not is_coordinator(request.user):
        asignaturas = asignaturas.exclude(nombre__iexact='TFG')

    asignaturas = asignaturas.order_by('nombre').values('id', 'nombre')
    
    return JsonResponse(list(asignaturas), safe=False)