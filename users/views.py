from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import StudentSubjectForm, NotificationForm
from schedule.models import Actividad
from academics.models import Titulacion, Asignatura
from django.core.mail import send_mail
from .models import CustomUser

def is_teacher(user):
    return user.is_authenticated and user.role in ['TEACHER', 'COORDINATOR', 'ADMIN']

def is_student(user):
    return user.is_authenticated and user.role == 'STUDENT'

def is_coordinator(user):
    return user.is_authenticated and user.role in ['COORDINATOR', 'ADMIN']

def is_admin(user):
    return user.is_authenticated and user.role == 'ADMIN'

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            email_domain = user.email.split('@')[-1]
            if email_domain == 'unex.es':
                user.role = 'TEACHER'
            elif email_domain == 'alumnos.unex.es':
                user.role = 'STUDENT'
            else:
                user.role = 'STUDENT'
            user.save()
            send_mail(
                'Welcome to Agenda Academica',
                'Thank you for registering. Your account has been created.',
                'from@example.com',
                [user.email],
                fail_silently=False,
            )
            return redirect('login')  # Redirect to login page after successful registration
    else:
        form = UserCreationForm()
    return render(request, 'users/registration.html', {'form': form})

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    titulaciones = Titulacion.objects.all()
    return render(request, 'users/teacher_dashboard.html', {'titulaciones': titulaciones})

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    user_subjects = request.user.subjects.all()
    activities = Actividad.objects.filter(asignatura__in=user_subjects).order_by('fecha_inicio')
    return render(request, 'users/student_dashboard.html', {'activities': activities})

@login_required
@user_passes_test(is_student)
def select_subjects(request):
    if request.method == 'POST':
        form = StudentSubjectForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('student_dashboard')
    else:
        form = StudentSubjectForm(instance=request.user)
    return render(request, 'users/select_subjects.html', {'form': form})

@login_required
@user_passes_test(is_coordinator)
def coordinator_dashboard(request):
    titulaciones = Titulacion.objects.all()
    selected_titulacion_id = request.GET.get('titulacion')
    selected_semestre = request.GET.get('semestre')

    activities = Actividad.objects.all()

    if selected_titulacion_id:
        activities = activities.filter(asignatura__titulacion__id=selected_titulacion_id)
    if selected_semestre:
        activities = activities.filter(asignatura__semestre=selected_semestre)

    return render(request, 'users/coordinator_dashboard.html', {
        'titulaciones': titulaciones,
        'activities': activities,
        'selected_titulacion_id': selected_titulacion_id,
        'selected_semestre': selected_semestre,
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
def dashboard_redirect(request):
    if request.user.role == 'ADMIN':
        return render(request, 'users/dashboard_selection.html', {'dashboards': {'Admin': 'admin:index', 'Coordinator': 'coordinator_dashboard', 'Teacher': 'teacher_dashboard'}})
    elif request.user.role == 'COORDINATOR':
        return render(request, 'users/dashboard_selection.html', {'dashboards': {'Coordinator': 'coordinator_dashboard', 'Teacher': 'teacher_dashboard'}})
    elif request.user.role == 'TEACHER':
        return redirect('teacher_dashboard')
    elif request.user.role == 'STUDENT':
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
    activities = Actividad.objects.filter(asignatura__in=user_subjects).order_by('fecha_inicio')
    return render(request, 'users/teacher_student_view.html', {'activities': activities})
