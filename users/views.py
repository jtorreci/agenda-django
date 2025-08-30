from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import StudentSubjectForm, NotificationForm
from schedule.models import Actividad, VistaCalendario, TipoActividad, LogActividad
from schedule.forms import VistaCalendarioForm
from academics.models import Titulacion, Asignatura
from django.core.mail import send_mail
from django.utils.translation import gettext as _
from .models import CustomUser
from django.contrib import messages
from django.http import JsonResponse
from agenda_academica.models import AgendaSettings
from django.views.decorators.http import require_http_methods
import json
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from .models import LoginAttempt
from django.conf import settings # Import settings

def is_teacher(user):
    return user.is_authenticated and user.role in [CustomUser.ROLE_TEACHER, CustomUser.ROLE_COORDINATOR, CustomUser.ROLE_ADMIN]

def is_student(user):
    return user.is_authenticated and user.role == CustomUser.ROLE_STUDENT

def is_coordinator(user):
    return user.is_authenticated and user.role in [CustomUser.ROLE_COORDINATOR, CustomUser.ROLE_ADMIN]

def is_admin(user):
    return user.role == CustomUser.ROLE_ADMIN or user.is_superuser

def is_coordinator_or_admin(user):
    return user.role == CustomUser.ROLE_COORDINATOR or user.role == CustomUser.ROLE_ADMIN or user.is_superuser

@login_required
@user_passes_test(is_admin)
def login_attempts(request):
    attempts = LoginAttempt.objects.all().order_by('-timestamp')
    return render(request, 'users/login_attempts.html', {'attempts': attempts})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            email_domain = user.email.split('@')[-1]

            # Check email domain for role assignment and validation
            if email_domain in settings.TEACHER_EMAIL_DOMAINS:
                user.role = CustomUser.ROLE_TEACHER
            elif email_domain in settings.STUDENT_EMAIL_DOMAINS:
                user.role = CustomUser.ROLE_STUDENT
            else:
                messages.error(request, _('Registration is only allowed for email addresses from UNEX (unex.es or alumnos.unex.es).'))
                return render(request, 'users/registration.html', {'form': form})

            user.save()

            # Send confirmation email
            current_site = get_current_site(request)
            mail_subject = _('Activate your account')
            message = render_to_string('users/account_activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            send_mail(mail_subject, message, 'from@example.com', [user.email])
            
            messages.success(request, _('Please check your email to complete the registration.'))
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'users/registration.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, _('Your account has been activated successfully. You can now log in.'))
        return redirect('login')
    else:
        messages.error(request, _('The activation link is invalid.'))
        return redirect('login')

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    teacher_subjects = request.user.subjects.all()
    
    titulaciones = Titulacion.objects.filter(asignatura__in=teacher_subjects).distinct()
    cursos = teacher_subjects.order_by('curso').values_list('curso', flat=True).distinct()
    semestres = teacher_subjects.order_by('semestre').values_list('semestre', flat=True).distinct()
    tipos_actividad = TipoActividad.objects.all() # Teachers can see all types of activities

    selected_titulaciones = request.GET.getlist('titulacion')
    selected_asignaturas = request.GET.getlist('asignatura')
    selected_cursos = request.GET.getlist('curso')
    selected_semestres = request.GET.getlist('semestre')
    selected_tipos_actividad = request.GET.getlist('tipo_actividad')

    activities = Actividad.objects.filter(asignaturas__in=teacher_subjects)

    if selected_titulaciones:
        activities = activities.filter(asignaturas__titulacion__id__in=selected_titulaciones)
    if selected_asignaturas:
        activities = activities.filter(asignaturas__id__in=selected_asignaturas)
    if selected_cursos:
        activities = activities.filter(asignaturas__curso__in=selected_cursos)
    if selected_semestres:
        activities = activities.filter(asignaturas__semestre__in=selected_semestres)
    if selected_tipos_actividad:
        activities = activities.filter(tipo_actividad__id__in=selected_tipos_actividad)

    calendar_views = VistaCalendario.objects.filter(usuario=request.user)

    return render(request, 'users/teacher_dashboard.html', {
        'titulaciones': titulaciones,
        'asignaturas': teacher_subjects,
        'cursos': cursos,
        'semestres': semestres,
        'tipos_actividad': tipos_actividad,
        'activities': activities.distinct(),
        'selected_titulaciones': selected_titulaciones,
        'selected_asignaturas': selected_asignaturas,
        'selected_cursos': selected_cursos,
        'selected_semestres': selected_semestres,
        'selected_tipos_actividad': selected_tipos_actividad,
        'teacher_subjects': teacher_subjects,
        'calendar_views': calendar_views,
    })

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    user_subjects = request.user.subjects.all()
    
    titulaciones = Titulacion.objects.filter(asignatura__in=user_subjects).distinct()
    cursos = user_subjects.order_by('curso').values_list('curso', flat=True).distinct()
    semestres = user_subjects.order_by('semestre').values_list('semestre', flat=True).distinct()
    tipos_actividad = TipoActividad.objects.all() # Students can see all types of activities

    selected_titulaciones = request.GET.getlist('titulacion')
    selected_asignaturas = request.GET.getlist('asignatura')
    selected_cursos = request.GET.getlist('curso')
    selected_semestres = request.GET.getlist('semestre')
    selected_tipos_actividad = request.GET.getlist('tipo_actividad')

    # Only show active and approved activities
    activities = Actividad.objects.filter(
        asignaturas__in=user_subjects,
        activa=True,
        aprobada=True
    )

    # Filter by selected subjects (if any are selected)
    if selected_asignaturas:
        # Filter by selected subjects from user's enrolled subjects
        selected_subjects = user_subjects.filter(id__in=selected_asignaturas)
        activities = activities.filter(asignaturas__in=selected_subjects)
    
    if selected_titulaciones:
        activities = activities.filter(asignaturas__titulacion__id__in=selected_titulaciones)
    if selected_cursos:
        activities = activities.filter(asignaturas__curso__in=selected_cursos)
    if selected_semestres:
        activities = activities.filter(asignaturas__semestre__in=selected_semestres)
    if selected_tipos_actividad:
        activities = activities.filter(tipo_actividad__id__in=selected_tipos_actividad)

    # Get user's calendar views for iCal feeds section
    calendar_views = VistaCalendario.objects.filter(usuario=request.user)

    return render(request, 'users/student_dashboard.html', {
        'titulaciones': titulaciones,
        'asignaturas': user_subjects,
        'enrolled_subjects': user_subjects,  # Add this for the sidebar
        'cursos': cursos,
        'semestres': semestres,
        'tipos_actividad': tipos_actividad,
        'activities': activities.distinct(),
        'calendar_views': calendar_views,  # Add this for iCal feeds section
        'selected_titulaciones': selected_titulaciones,
        'selected_asignaturas': selected_asignaturas,
        'selected_cursos': selected_cursos,
        'selected_semestres': selected_semestres,
        'selected_tipos_actividad': selected_tipos_actividad,
    })

@login_required
@user_passes_test(is_student)
def select_subjects(request):
    # --- Lógica para guardar la selección (POST) ---
    if request.method == 'POST':
        # Obtenemos la lista de IDs de las asignaturas seleccionadas
        subject_ids = request.POST.getlist('subjects')
        
        # Limpiamos las asignaturas anteriores del usuario
        request.user.subjects.clear()
        
        # Añadimos las nuevas asignaturas seleccionadas
        if subject_ids:
            request.user.subjects.add(*subject_ids)
            
        return redirect('student_dashboard')

    # --- Lógica para mostrar la página (GET) ---
    # 1. Obtiene SIEMPRE todas las titulaciones para el menú desplegable.
    todas_las_titulaciones = Titulacion.objects.all()

    # 2. Comprueba si el usuario ha seleccionado una titulación desde el menú
    selected_titulacion_id = request.GET.get('titulacion')
    
    asignaturas_by_curso = {}
    
    if selected_titulacion_id:
        # 3. Si se seleccionó una titulación, busca y agrupa sus asignaturas
        asignaturas = Asignatura.objects.filter(titulacion_id=selected_titulacion_id).order_by('curso', 'semestre', 'nombre')
        
        for a in asignaturas:
            curso_key = f"Curso {a.curso}"
            if curso_key not in asignaturas_by_curso:
                asignaturas_by_curso[curso_key] = {'primer_semestre': [], 'segundo_semestre': [], 'optativas': []}
            
            if a.semestre == 1:
                asignaturas_by_curso[curso_key]['primer_semestre'].append(a)
            elif a.semestre == 2:
                asignaturas_by_curso[curso_key]['segundo_semestre'].append(a)
            else: # Asumimos que otros valores son optativas
                 asignaturas_by_curso[curso_key]['optativas'].append(a)

    # 4. Prepara el contexto con todos los datos que la plantilla necesita
    context = {
        'titulaciones': todas_las_titulaciones,
        'selected_titulacion_id': selected_titulacion_id,
        'asignaturas_by_curso': asignaturas_by_curso,
        'student_enrolled_ids': list(request.user.subjects.all().values_list('id', flat=True)),
    }

    return render(request, 'users/select_subjects.html', context)

@login_required
@user_passes_test(is_student)
def student_ical_config(request):
    if request.method == 'POST':
        form = VistaCalendarioForm(request.POST, user=request.user)
        if form.is_valid():
            calendar_view = form.save(commit=False)
            calendar_view.usuario = request.user
            calendar_view.save()
            form.save_m2m() # Save ManyToMany relationships
            return redirect('student_dashboard') # Redirect to student dashboard after creating
    else:
        form = VistaCalendarioForm(user=request.user)
    
    # Also display existing calendar views for the student
    calendar_views = VistaCalendario.objects.filter(usuario=request.user)
    
    return render(request, 'users/student_ical_config.html', {
        'form': form,
        'calendar_views': calendar_views
    })

@login_required
@user_passes_test(is_student)
def student_calendar_events(request):
    """
    Esta vista devuelve los eventos del estudiante logueado en formato JSON
    para que FullCalendar los pueda mostrar.
    """
    # 1. Obtener las asignaturas del estudiante actual
    enrolled_subjects = request.user.subjects.all()

    # 2. Check if specific subjects are selected for filtering
    selected_asignaturas = request.GET.getlist('asignatura')
    if selected_asignaturas:
        # Filter by selected subjects from user's enrolled subjects
        enrolled_subjects = enrolled_subjects.filter(id__in=selected_asignaturas)

    # 3. Filtrar las actividades de esas asignaturas (sin duplicados)
    # Solo mostrar actividades activas y aprobadas
    activities = Actividad.objects.filter(
        asignaturas__in=enrolled_subjects,
        activa=True,
        aprobada=True
    ).distinct()

    # 4. Formatear los datos para FullCalendar
    events = []
    from agenda_academica.models import AgendaSettings
    from django.utils import timezone

    # Load the closing date
    try:
        closing_date = AgendaSettings.load().closing_date
    except Exception:
        # Fallback if AgendaSettings is not configured or an error occurs
        closing_date = timezone.now().date()

    for activity in activities:
        event_class_names = []
        if activity.fecha_inicio.date() < closing_date:
            event_class_names.append('past-event')
        else:
            event_class_names.append('future-event')

        # Get assigned subject names
        subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])

        events.append({
            'id': activity.id, # Add activity ID for eventClick
            'title': activity.nombre,
            'start': activity.fecha_inicio.isoformat(), # Formato estándar ISO 8601
            'end': activity.fecha_fin.isoformat(),
            'classNames': event_class_names, # Add class for styling
            'extendedProps': { # Add more details for eventClick
                'description': activity.descripcion,
                'activity_type': activity.tipo_actividad.nombre,
                'subjects': subject_names,
                'is_approved': activity.aprobada,
                'is_active': activity.activa,
                'evaluable': activity.evaluable,
                'percentage': activity.porcentaje_evaluacion,
            }
        })

    # 4. Devolver los datos como una respuesta JSON
    return JsonResponse(events, safe=False)

@login_required
@user_passes_test(is_coordinator)
def coordinator_dashboard(request):
    # Get titulaciones coordinated by the current user
    user_coordinated_titulaciones = Titulacion.objects.filter(coordinador=request.user)

    # Always show all titulaciones in the filter dropdown
    titulaciones = Titulacion.objects.all()
    asignaturas = Asignatura.objects.all() # All asignaturas for filter
    
    # Get unique courses and semesters with human-readable labels
    curso_values = Asignatura.objects.order_by('curso').values_list('curso', flat=True).distinct()
    cursos_with_labels = []
    for curso in curso_values:
        if curso == 10:
            label = "Optativa"
        elif curso == 1000:
            label = "TFE"
        else:
            label = str(curso)
        cursos_with_labels.append({'value': curso, 'label': label})
    
    semestres = Asignatura.objects.order_by('semestre').values_list('semestre', flat=True).distinct()
    tipos_actividad = TipoActividad.objects.all()

    # Get selected filters from request
    selected_titulaciones = request.GET.getlist('titulacion')
    selected_asignaturas = request.GET.getlist('asignatura')
    selected_cursos = request.GET.getlist('curso')
    selected_semestres = request.GET.getlist('semestre')
    selected_tipos_actividad = request.GET.getlist('tipo_actividad')
    
    # New filters
    filter_evaluable = request.GET.get('filter_evaluable') == 'on'
    min_percentage = request.GET.get('min_percentage')
    approval_status = request.GET.get('approval_status') # 'approved', 'unapproved', 'all'

    # Initial queryset: all activities
    activities = Actividad.objects.all()

    # Apply filters from the form
    if selected_titulaciones:
        activities = activities.filter(asignaturas__titulacion__id__in=selected_titulaciones)
    if selected_asignaturas:
        activities = activities.filter(asignaturas__id__in=selected_asignaturas)
    if selected_cursos:
        activities = activities.filter(asignaturas__curso__in=selected_cursos)
    if selected_semestres:
        activities = activities.filter(asignaturas__semestre__in=selected_semestres)
    if selected_tipos_actividad:
        activities = activities.filter(tipo_actividad__id__in=selected_tipos_actividad)

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
    
    # Filter activities by coordinator's assigned titulaciones for display in the table
    # This ensures only activities related to coordinated titulaciones are shown in the table
    # and their checkboxes are editable.
    if not request.user.role == 'ADMIN': # Admins see all activities
        activities = activities.filter(asignaturas__titulacion__in=user_coordinated_titulaciones).distinct()


    # Check if user has any coordinated titulaciones
    show_no_titulaciones_message = not user_coordinated_titulaciones.exists() and request.user.role != 'ADMIN'

    return render(request, 'users/coordinator_dashboard.html', {
        'titulaciones': titulaciones, # All titulaciones for filter dropdown
        'asignaturas': asignaturas, # All asignaturas for filter dropdown
        'cursos': cursos_with_labels,
        'semestres': semestres,
        'tipos_actividad': tipos_actividad,
        'activities': activities.distinct(),
        'selected_titulaciones': selected_titulaciones,
        'selected_asignaturas': selected_asignaturas,
        'selected_cursos': selected_cursos,
        'selected_semestres': selected_semestres,
        'selected_tipos_actividad': selected_tipos_actividad,
        'filter_evaluable': filter_evaluable,
        'min_percentage': min_percentage,
        'approval_status': approval_status,
        'user_coordinated_titulaciones_ids': [t.id for t in user_coordinated_titulaciones], # Pass IDs for frontend check
        'show_no_titulaciones_message': show_no_titulaciones_message,
    })

@login_required
@user_passes_test(is_coordinator)
def send_notification(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            # Send email to all users
            for user in CustomUser.objects.all():
                send_mail(
                    subject,
                    message,
                    'from@example.com',
                    [user.email],
                    fail_silently=False,
                )
            return redirect('coordinator_dashboard')
    else:
        form = NotificationForm()
    return render(request, 'users/send_notification.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def kpi_report(request):
    total_users = CustomUser.objects.count()
    total_teachers = CustomUser.objects.filter(role='TEACHER').count()
    total_students = CustomUser.objects.filter(role='STUDENT').count()
    total_activities = Actividad.objects.count()
    total_titulaciones = Titulacion.objects.count()

    return render(request, 'users/kpi_report.html', {
        'total_users': total_users,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'total_activities': total_activities,
        'total_titulaciones': total_titulaciones,
    })

@login_required
@user_passes_test(is_admin)
def assign_coordinators(request):
    if request.method == 'POST':
        # Get current coordinator assignments before changes
        current_coordinators = set(Titulacion.objects.filter(
            coordinador__isnull=False
        ).values_list('coordinador', flat=True))
        
        new_coordinators = set()
        
        # Process form submission
        for key, value in request.POST.items():
            if key.startswith('coordinator_'):
                titulacion_id = key.replace('coordinator_', '')
                try:
                    titulacion = Titulacion.objects.get(id=titulacion_id)
                    if value:  # If a coordinator was selected
                        coordinator = CustomUser.objects.get(id=value)
                        titulacion.coordinador = coordinator
                        new_coordinators.add(coordinator.id)
                        
                        # Ensure the assigned user has COORDINATOR role (unless they're ADMIN)
                        if coordinator.role not in [CustomUser.ROLE_COORDINATOR, CustomUser.ROLE_ADMIN]:
                            coordinator.role = CustomUser.ROLE_COORDINATOR
                            coordinator.save()
                    else:  # If no coordinator selected (empty option)
                        titulacion.coordinador = None
                    titulacion.save()
                except (Titulacion.DoesNotExist, CustomUser.DoesNotExist):
                    continue
        
        # Remove COORDINATOR role from users who are no longer coordinators
        users_to_remove_role = current_coordinators - new_coordinators
        for user_id in users_to_remove_role:
            try:
                user = CustomUser.objects.get(id=user_id)
                # Only remove COORDINATOR role if they're not ADMIN and not coordinating any titulacion
                if (user.role == CustomUser.ROLE_COORDINATOR and 
                    not Titulacion.objects.filter(coordinador=user).exists()):
                    # Demote to TEACHER role (or keep as STUDENT if they were STUDENT originally)
                    # We'll default to TEACHER since coordinators are usually teachers
                    user.role = CustomUser.ROLE_TEACHER
                    user.save()
            except CustomUser.DoesNotExist:
                continue
        
        messages.success(request, 'Coordinadores asignados correctamente y roles actualizados.')
        return redirect('assign_coordinators')
    
    # GET request - display the form
    titulaciones = Titulacion.objects.all().order_by('nombre')
    # Show all users for selection
    all_users = CustomUser.objects.all().order_by('username')
    
    return render(request, 'users/assign_coordinators.html', {
        'titulaciones': titulaciones,
        'all_users': all_users,
    })

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    from agenda_academica.models import AgendaSettings
    
    total_users = CustomUser.objects.count()
    total_teachers = CustomUser.objects.filter(role='TEACHER').count()
    total_students = CustomUser.objects.filter(role='STUDENT').count()
    total_activities = Actividad.objects.count()
    total_titulaciones = Titulacion.objects.count()
    total_asignaturas = Asignatura.objects.count()
    active_activities = Actividad.objects.filter(activa=True).count()
    
    titulaciones = Titulacion.objects.all().order_by('nombre')
    all_users = CustomUser.objects.all().order_by('username')
    tipos_actividad = TipoActividad.objects.all()
    logs = LogActividad.objects.all().order_by('-timestamp')[:50]
    
    try:
        settings = AgendaSettings.load()
    except:
        settings = None
    
    context = {
        'total_users': total_users,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'total_activities': total_activities,
        'total_titulaciones': total_titulaciones,
        'total_asignaturas': total_asignaturas,
        'active_activities': active_activities,
        'titulaciones': titulaciones,
        'all_titulaciones': titulaciones,  # For PDF report dropdown
        'all_users': all_users,
        'tipos_actividad': tipos_actividad,
        'logs': logs,
        'settings': settings,
    }
    
    return render(request, 'users/admin_dashboard.html', context)

@login_required
def dashboard_redirect(request):
    if request.user.role == CustomUser.ROLE_ADMIN:
        return redirect('admin_dashboard')
    elif request.user.role == CustomUser.ROLE_COORDINATOR:
        return render(request, 'users/dashboard_selection.html', {'dashboards': {'Coordinator': 'coordinator_dashboard', 'Teacher': 'teacher_dashboard'}})
    elif request.user.role == CustomUser.ROLE_TEACHER:
        return redirect('teacher_dashboard')
    elif request.user.role == CustomUser.ROLE_STUDENT:
        return redirect('student_dashboard')
    else:
        return redirect('home')

@login_required
@user_passes_test(is_teacher)
def teacher_select_subjects(request):
    titulaciones = Titulacion.objects.all()
    selected_titulacion_id = request.GET.get('titulacion')
    
    asignaturas_by_curso = {}
    if selected_titulacion_id:
        asignaturas = Asignatura.objects.filter(titulacion_id=selected_titulacion_id).order_by('curso', 'semestre', 'nombre')
        
        curso_map = {
            1: "Primer Curso", 2: "Segundo Curso", 3: "Tercer Curso", 4: "Cuarto Curso",
        }

        optativas_tfe_key = "Optativas y TFE"

        for asignatura in asignaturas:
            curso = asignatura.curso
            
            if curso >= 10:
                curso_display = optativas_tfe_key
            else:
                curso_display = curso_map.get(curso, f"Curso {curso}")

            if curso_display not in asignaturas_by_curso:
                asignaturas_by_curso[curso_display] = {'primer_semestre': [], 'segundo_semestre': [], 'optativas': []}
            
            if asignatura.semestre == 1:
                asignaturas_by_curso[curso_display]['primer_semestre'].append(asignatura)
            elif asignatura.semestre == 2:
                asignaturas_by_curso[curso_display]['segundo_semestre'].append(asignatura)
            else:
                asignaturas_by_curso[curso_display]['optativas'].append(asignatura)

    if request.method == 'POST':
        subject_ids = request.POST.getlist('subjects')
        request.user.subjects.set(subject_ids)
        return redirect(request.get_full_path())
    
    context = {
        'titulaciones': titulaciones,
        'selected_titulacion_id': selected_titulacion_id,
        'asignaturas_by_curso': asignaturas_by_curso,
        'user_subjects_ids': list(request.user.subjects.all().values_list('id', flat=True)),
    }
    return render(request, 'users/teacher_select_subjects.html', context)

@login_required
@user_passes_test(is_teacher)
def teacher_student_view(request):
    user_subjects = request.user.subjects.all()
    activities = Actividad.objects.filter(asignaturas__in=user_subjects).order_by('fecha_inicio')
    return render(request, 'users/teacher_student_view.html', {'activities': activities})

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
@require_http_methods(["PUT"])
def ajax_update_coordinator(request):
    try:
        data = json.loads(request.body)
        titulacion_id = data.get('titulacion_id')
        coordinator_id = data.get('coordinator_id')  # Can be None to remove coordinator
        
        if not titulacion_id:
            return JsonResponse({'success': False, 'error': 'ID de titulación requerido'})
        
        try:
            titulacion = Titulacion.objects.get(id=titulacion_id)
        except Titulacion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Titulación no encontrada'})
        
        # Get current coordinator before change
        current_coordinator = titulacion.coordinador
        
        # Update coordinator
        if coordinator_id:
            try:
                new_coordinator = CustomUser.objects.get(id=coordinator_id)
                titulacion.coordinador = new_coordinator
                titulacion.save()
                
                # Ensure the assigned user has COORDINATOR role (unless they're ADMIN)
                if new_coordinator.role not in [CustomUser.ROLE_COORDINATOR, CustomUser.ROLE_ADMIN]:
                    new_coordinator.role = CustomUser.ROLE_COORDINATOR
                    new_coordinator.save()
                
                coordinator_info = {
                    'id': new_coordinator.id,
                    'username': new_coordinator.username,
                    'full_name': f"{new_coordinator.first_name} {new_coordinator.last_name}".strip() or new_coordinator.username
                }
                
                # Log the coordinator assignment
                if current_coordinator:
                    details = f'Coordinator for "{titulacion.nombre}" changed from {current_coordinator.username} to {new_coordinator.username}'
                    action = 'Modificación'
                else:
                    details = f'Coordinator {new_coordinator.username} assigned to "{titulacion.nombre}"'
                    action = 'Asignación'
                    
                LogActividad.objects.create(
                    object_type='coordinador',
                    object_name=titulacion.nombre,
                    object_id=titulacion.id,
                    usuario=request.user,
                    tipo_log=action,
                    details=details
                )
                
            except CustomUser.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Usuario no encontrado'})
        else:
            # Remove coordinator
            if current_coordinator:
                # Log the coordinator removal
                LogActividad.objects.create(
                    object_type='coordinador',
                    object_name=titulacion.nombre,
                    object_id=titulacion.id,
                    usuario=request.user,
                    tipo_log='Eliminación',
                    details=f'Coordinator {current_coordinator.username} removed from "{titulacion.nombre}"'
                )
                
            titulacion.coordinador = None
            titulacion.save()
            coordinator_info = None
        
        # Check if we need to remove COORDINATOR role from previous coordinator
        if current_coordinator and current_coordinator.id != coordinator_id:
            if (current_coordinator.role == CustomUser.ROLE_COORDINATOR and 
                not Titulacion.objects.filter(coordinador=current_coordinator).exists()):
                # Demote to TEACHER role since coordinators are usually teachers
                current_coordinator.role = CustomUser.ROLE_TEACHER
                current_coordinator.save()
        
        return JsonResponse({
            'success': True,
            'titulacion_id': titulacion_id,
            'coordinator': coordinator_info
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON inválidos'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
