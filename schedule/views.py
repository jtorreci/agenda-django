from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from users.views import is_teacher, is_coordinator
from .forms import ActividadForm, VistaCalendarioForm
from .models import Actividad, VistaCalendario
from icalendar import Calendar, Event
from django.http import HttpResponse, JsonResponse
from academics.models import Asignatura
from django.core import serializers

@login_required
@user_passes_test(is_teacher)
def activity_form(request, pk=None):
    activity = None # Initialize activity to None
    if pk:
        activity = get_object_or_404(Actividad, pk=pk)
        initial_subjects = activity.asignaturas.all()
    else:
        subject_ids_str = request.GET.get('subjects')
        initial_subjects = []
        if subject_ids_str:
            subject_ids = [int(s_id) for s_id in subject_ids_str.split(',') if s_id.isdigit()]
            initial_subjects = Asignatura.objects.filter(id__in=subject_ids)

    if request.method == 'POST':
        form = ActividadForm(request.POST, instance=activity, user=request.user)
        if form.is_valid():
            activity = form.save()
            return redirect('teacher_dashboard')
    else: # GET request
        if activity: # If editing an existing activity
            form = ActividadForm(instance=activity, user=request.user)
        else: # If creating a new activity
            form = ActividadForm(initial={'asignaturas': initial_subjects}, user=request.user)

    return render(request, 'schedule/activity_form.html', {'form': form})

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
def get_filtered_activities(request):
    subject_ids_str = request.GET.get('subject_ids')
    if not subject_ids_str:
        return JsonResponse({'activities': []})

    subject_ids = [int(s_id) for s_id in subject_ids_str.split(',') if s_id.isdigit()]
    
    # Get all activities that are linked to any of the selected subjects
    # Use a dictionary to maintain order and uniqueness by ID
    unique_activities = {}
    for activity in Actividad.objects.filter(asignaturas__id__in=subject_ids).order_by('fecha_inicio'):
        unique_activities[activity.id] = activity

    activities_to_serialize = list(unique_activities.values())

    # Manually serialize the data to include related fields
    activities_data = []
    for activity in activities_to_serialize:
        activities_data.append({
            'id': activity.id,
            'nombre': activity.nombre,
            'fecha_inicio': activity.fecha_inicio.isoformat(),
            'fecha_fin': activity.fecha_fin.isoformat(),
            'descripcion': activity.descripcion,
            'tipo_actividad': activity.tipo_actividad.nombre,
            'asignaturas': [a.nombre for a in activity.asignaturas.all()],
            'evaluable': activity.evaluable,
            'aprobada': activity.aprobada
        })
    
    return JsonResponse({'activities': activities_data})

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
        form = VistaCalendarioForm(request.POST, user=request.user)
        if form.is_valid():
            calendar_view = form.save(commit=False)
            calendar_view.usuario = request.user
            calendar_view.save()
            form.save_m2m() # Save ManyToMany relationships
            return redirect('teacher_dashboard')
    else:
        form = VistaCalendarioForm(user=request.user)
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
        activities = activities.filter(asignaturas__in=calendar_view.asignaturas.all())
    if calendar_view.tipos_actividad.exists():
        activities = activities.filter(tipo_actividad__in=calendar_view.tipos_actividad.all())

    for activity in activities_to_serialize:
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