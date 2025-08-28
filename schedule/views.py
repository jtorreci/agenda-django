from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import transaction
from django.http import HttpResponseRedirect
from users.views import is_teacher, is_coordinator, is_coordinator_or_admin
from .forms import ActividadForm, VistaCalendarioForm
from .models import Actividad, VistaCalendario, LogActividad, TipoActividad
from icalendar import Calendar, Event
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from academics.models import Asignatura, Titulacion
from django.core import serializers
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

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
            is_new_activity = activity is None
            activity = form.save()
            if is_new_activity:
                LogActividad.objects.create(
                    actividad=activity,
                    usuario=request.user,
                    tipo_log='Creación'
                )
            else:
                LogActividad.objects.create(
                    actividad=activity,
                    usuario=request.user,
                    tipo_log='Modificación'
                )
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
        activity.activa = False
        activity.save()
        LogActividad.objects.create(
            actividad=activity,
            usuario=request.user,
            tipo_log='Borrado'
        )
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
@user_passes_test(is_coordinator_or_admin)
def activity_logs(request):
    logs = LogActividad.objects.all().order_by('-timestamp')
    return render(request, 'schedule/activity_logs.html', {'logs': logs})

@login_required
@user_passes_test(is_coordinator_or_admin)
def reactivate_activity(request, pk):
    activity = get_object_or_404(Actividad, pk=pk)
    if request.method == 'POST':
        activity.activa = True
        activity.save()
        LogActividad.objects.create(
            actividad=activity,
            usuario=request.user,
            tipo_log='Reactivación'
        )
        return redirect('activity_logs')
    # If it's a GET request, render a confirmation page (optional, but good practice)
    return render(request, 'schedule/activity_confirm_reactivate.html', {'activity': activity})

@login_required
@user_passes_test(is_coordinator_or_admin)
def toggle_activity_approval(request, pk):
    activity = get_object_or_404(Actividad, pk=pk)
    if request.method == 'POST':
        new_status = not activity.aprobada
        activity.set_approval_manually(new_status)
        
        log_type = 'Aprobación' if new_status else 'Desaprobación'
        LogActividad.objects.create(
            actividad=activity,
            usuario=request.user,
            tipo_log=log_type
        )
        return redirect('activity_logs')
    # If it's a GET request, render a confirmation page (optional)
    return render(request, 'schedule/activity_confirm_approval_toggle.html', {'activity': activity})

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

    for activity in activities.distinct():
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

@csrf_exempt # Temporarily for testing, should use proper CSRF handling in production
@require_POST
@login_required
@user_passes_test(is_coordinator) # Only coordinators can approve
def toggle_activity_approval_from_dashboard(request, pk):
    try:
        activity = Actividad.objects.get(pk=pk)
        data = json.loads(request.body)
        new_status = data.get('aprobada')

        # Permission check: Coordinator can only approve activities for their coordinated titulaciones
        user_coordinated_titulaciones = Titulacion.objects.filter(coordinador=request.user)
        activity_titulaciones = Titulacion.objects.filter(asignatura__in=activity.asignaturas.all()).distinct()

        # Check if any of the activity's titulaciones are coordinated by the user
        can_approve = False
        if request.user.role == 'ADMIN': # Admins can approve all
            can_approve = True
        else:
            for act_tit in activity_titulaciones:
                if act_tit in user_coordinated_titulaciones:
                    can_approve = True
                    break
        
        if not can_approve:
            return JsonResponse({'success': False, 'error': 'You do not have permission to approve activities for this titulacion.'}, status=403)

        activity.set_approval_manually(new_status)

        log_type = 'Aprobación desde Dashboard' if new_status else 'Desaprobación desde Dashboard'
        LogActividad.objects.create(
            actividad=activity,
            usuario=request.user,
            tipo_log=log_type
        )
        return JsonResponse({'success': True})
    except Actividad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Activity not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_filtered_asignaturas(request):
    titulacion_ids = request.GET.getlist('titulacion_ids[]')
    curso_ids = request.GET.getlist('curso_ids[]')
    print(f"DEBUG: get_filtered_asignaturas received titulacion_ids: {titulacion_ids}, curso_ids: {curso_ids}")

    asignaturas = Asignatura.objects.all()

    if titulacion_ids:
        asignaturas = asignaturas.filter(titulacion__id__in=titulacion_ids).distinct()
    if curso_ids:
        asignaturas = asignaturas.filter(curso__in=curso_ids).distinct()

    data = [{'id': asignatura.id, 'nombre': asignatura.nombre} for asignatura in asignaturas]
    return JsonResponse(data, safe=False)

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

def all_activities(request):
    print(f"Received GET parameters: {request.GET}") # Debug print

    activities = Actividad.objects.all()
    
    titulaciones = request.GET.getlist('titulacion')
    cursos = request.GET.getlist('curso')
    semestres = request.GET.getlist('semestre')
    asignaturas = request.GET.getlist('asignatura')
    tipos_actividad = request.GET.getlist('tipo_actividad')

    filter_evaluable = request.GET.get('filter_evaluable') == 'on'
    min_percentage = request.GET.get('min_percentage')
    approval_status = request.GET.get('approval_status')

    if titulaciones:
        activities = activities.filter(asignaturas__titulacion__id__in=titulaciones)
    if cursos:
        activities = activities.filter(asignaturas__curso__in=cursos)
    if semestres:
        activities = activities.filter(asignaturas__semestre__in=semestres)
    if asignaturas:
        print(f"DEBUG: all_activities received asignaturas: {asignaturas}")
        activities = activities.filter(asignaturas__id__in=asignaturas)
    if tipos_actividad:
        activities = activities.filter(tipo_actividad__id__in=tipos_actividad)

    # Apply new filters
    if filter_evaluable:
        activities = activities.filter(evaluable=True)
        if min_percentage:
            try:
                min_percentage = float(min_percentage)
                activities = activities.filter(porcentaje_evaluacion__gte=min_percentage)
            except ValueError:
                pass # Ignore invalid percentage

    if approval_status == 'approved':
        activities = activities.filter(aprobada=True)
    elif approval_status == 'unapproved':
        activities = activities.filter(aprobada=False)

    print(f"Filtered activities count: {activities.distinct().count()}") # Debug print

    data = []
    for activity in activities.distinct():
        data.append({
            'title': activity.nombre,
            'start': activity.fecha_inicio.isoformat(),
            'end': activity.fecha_fin.isoformat(),
        })
    return JsonResponse(data, safe=False)

class TipoActividadListView(ListView):
    model = TipoActividad
    template_name = 'schedule/tipoactividad_list.html'

class TipoActividadCreateView(CreateView):
    model = TipoActividad
    fields = ['nombre']
    template_name = 'schedule/tipoactividad_form.html'
    success_url = reverse_lazy('tipoactividad_list')

class TipoActividadUpdateView(UpdateView):
    model = TipoActividad
    fields = ['nombre']
    template_name = 'schedule/tipoactividad_form.html'
    success_url = reverse_lazy('tipoactividad_list')

class TipoActividadDeleteView(DeleteView):
    model = TipoActividad
    template_name = 'schedule/tipoactividad_confirm_delete.html'
    success_url = reverse_lazy('tipoactividad_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_actividad'] = TipoActividad.objects.exclude(pk=self.object.pk)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get('action')
        reassign_to_id = request.POST.get('reassign_to')

        if action == 'reassign' and reassign_to_id:
            try:
                reassign_to_type = TipoActividad.objects.get(pk=reassign_to_id)
                with transaction.atomic():
                    # Reassign activities
                    Actividad.objects.filter(tipo_actividad=self.object).update(tipo_actividad=reassign_to_type)
                    # Then delete the TipoActividad
                    self.object.delete()
                return HttpResponseRedirect(self.get_success_url())
            except TipoActividad.DoesNotExist:
                # Handle case where reassign_to_id is invalid
                pass # Or add an error message
        elif action == 'cascade':
            # Perform default cascade delete (Django's default behavior for DeleteView)
            self.object.delete()
            return HttpResponseRedirect(self.get_success_url())
        
        # If no valid action or reassign_to_id, re-render the form with context
        return self.get(request, *args, **kwargs)