from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import transaction
from django.http import HttpResponseRedirect
from users.views import is_teacher, is_coordinator, is_coordinator_or_admin
from .forms import ActividadForm, VistaCalendarioForm, MultiGroupActivityForm, UnifiedActivityForm
from .models import Actividad, ActividadGrupo, VistaCalendario, LogActividad, TipoActividad, ActividadVersion
from icalendar import Calendar, Event
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from agenda_academica.models import AgendaSettings
from academics.models import Asignatura, Titulacion
from django.core import serializers
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
from django.template.loader import get_template
from django.conf import settings
import json
import uuid
from datetime import datetime
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def get_user_dashboard_url(user):
    """Helper function to get the correct dashboard URL based on user role"""
    if user.role == 'TEACHER':
        return 'teacher_dashboard'
    elif user.role == 'COORDINATOR':
        return 'coordinator_dashboard'
    elif user.role == 'ADMIN':
        return 'admin_dashboard'
    else:
        return 'home'

@login_required
@user_passes_test(is_teacher)
def activity_form(request, pk=None, read_only=False): # Added read_only parameter
    activity = None # Initialize activity to None
    if pk:
        activity = get_object_or_404(Actividad, pk=pk)
        # IDOR check
        if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
            return redirect(get_user_dashboard_url(request.user))
        initial_subjects = activity.asignaturas.all()
    else:
        subject_ids_str = request.GET.get('subjects')
        initial_subjects = []
        if subject_ids_str:
            subject_ids = [int(s_id) for s_id in subject_ids_str.split(',') if s_id.isdigit()]
            initial_subjects = Asignatura.objects.filter(id__in=subject_ids)

    if request.method == 'POST' and not read_only: # Prevent saving if read_only
        form = ActividadForm(request.POST, instance=activity, user=request.user)
        if form.is_valid():
            is_new_activity = activity is None
            # Set metadata for versioning system before saving
            if not is_new_activity:
                activity = form.save(commit=False)
                activity._modified_by = request.user
                activity._version_comment = request.POST.get('version_comment', '')
                activity.save()
                # Need to save many-to-many relationships manually when using commit=False
                form.save_m2m()
            else:
                activity = form.save()
            if is_new_activity:
                LogActividad.objects.create(
                    object_type='actividad',
                    object_name=activity.nombre,
                    object_id=activity.id,
                    actividad=activity,  # Keep for backward compatibility
                    usuario=request.user,
                    tipo_log=_('Creation'),
                    details=_('Activity "%(name)s" created for %(count)d subject(s)') % {
                        'name': activity.nombre, 
                        'count': activity.asignaturas.count()
                    }
                )
            else:
                LogActividad.objects.create(
                    object_type='actividad',
                    object_name=activity.nombre,
                    object_id=activity.id,
                    actividad=activity,  # Keep for backward compatibility
                    usuario=request.user,
                    tipo_log=_('Modification'),
                    details=_('Activity "%(name)s" modified') % {'name': activity.nombre}
                )
            return redirect(get_user_dashboard_url(request.user))
    else: # GET request or POST with read_only=True
        if activity: # If editing an existing activity or viewing details
            form = ActividadForm(instance=activity, user=request.user, read_only=read_only) # Pass read_only
        else: # If creating a new activity
            form = ActividadForm(initial={'asignaturas': initial_subjects}, user=request.user, read_only=read_only) # Pass read_only

    return render(request, 'schedule/activity_form.html', {'form': form, 'read_only': read_only}) # Pass read_only to template

@login_required
@user_passes_test(is_teacher)
def activity_delete(request, pk):
    activity = get_object_or_404(Actividad, pk=pk)
    # IDOR check
    if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
        return redirect(get_user_dashboard_url(request.user))
    if request.method == 'POST':
        activity.activa = False
        activity.save()
        LogActividad.objects.create(
            actividad=activity,
            usuario=request.user,
            tipo_log=_('Deletion')
        )
        return redirect('teacher_dashboard')
    return render(request, 'schedule/activity_confirm_delete.html', {'activity': activity})

@login_required
@user_passes_test(is_teacher)
def activity_detail_view(request, pk):
    """
    Vista para mostrar los detalles completos de una actividad con opción de generar PDF
    """
    activity = get_object_or_404(Actividad, pk=pk)

    # IDOR check
    if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
        return redirect(get_user_dashboard_url(request.user))

    # Get activity groups if available
    grupos = activity.grupos.all().order_by('orden')

    context = {
        'activity': activity,
        'grupos': grupos,
        'is_multi_group': grupos.count() > 1,
    }

    return render(request, 'schedule/activity_detail.html', context)

@login_required
@user_passes_test(is_teacher)
def activity_pdf_convocatoria(request, pk):
    """
    Genera un PDF con formato de convocatoria oficial para una actividad
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from django.http import HttpResponse
    from django.utils import timezone
    import os

    activity = get_object_or_404(Actividad, pk=pk)

    # IDOR check
    if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
        return redirect(get_user_dashboard_url(request.user))

    # Create HTTP response with PDF content type
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="convocatoria_{activity.nombre.replace(" ", "_")}.pdf"'

    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=A4,
                          rightMargin=2*cm, leftMargin=2*cm,
                          topMargin=2*cm, bottomMargin=2*cm)

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6
    )

    # Build content
    content = []

    # Title
    content.append(Paragraph("CONVOCATORIA DE ACTIVIDAD", title_style))
    content.append(Spacer(1, 0.5*cm))

    # Activity basic info
    content.append(Paragraph("INFORMACIÓN GENERAL", subtitle_style))

    info_data = [
        ['Nombre de la Actividad:', activity.nombre],
        ['Tipo de Actividad:', activity.tipo_actividad.nombre],
        ['Fecha de Inicio:', activity.fecha_inicio.strftime('%d de %B de %Y, %H:%M')],
        ['Fecha de Fin:', activity.fecha_fin.strftime('%d de %B de %Y, %H:%M')],
    ]

    # Add subjects
    asignaturas = ', '.join([asig.nombre for asig in activity.asignaturas.all()])
    info_data.append(['Asignaturas:', asignaturas])

    # Add evaluation info if applicable
    if activity.evaluable:
        info_data.append(['Evaluable:', f'Sí ({activity.porcentaje_evaluacion}%)'])
        if activity.no_recuperable:
            info_data.append(['Recuperable:', 'No'])
        else:
            info_data.append(['Recuperable:', 'Sí'])
    else:
        info_data.append(['Evaluable:', 'No'])

    info_table = Table(info_data, colWidths=[5*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    content.append(info_table)
    content.append(Spacer(1, 0.5*cm))

    # Groups information (if multi-group)
    grupos = activity.grupos.all().order_by('orden')
    if grupos.exists():
        content.append(Paragraph("GRUPOS Y HORARIOS", subtitle_style))

        group_data = [['Grupo', 'Fecha/Hora Inicio', 'Fecha/Hora Fin', 'Lugar', 'Descripción']]
        for grupo in grupos:
            group_data.append([
                grupo.nombre_grupo,
                grupo.fecha_inicio.strftime('%d/%m/%Y %H:%M'),
                grupo.fecha_fin.strftime('%d/%m/%Y %H:%M'),
                grupo.lugar or 'No especificado',
                grupo.descripcion or '-'
            ])

        groups_table = Table(group_data, colWidths=[2*cm, 3.5*cm, 3.5*cm, 3*cm, 3*cm])
        groups_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        content.append(groups_table)
        content.append(Spacer(1, 0.5*cm))

    # Description
    if activity.descripcion:
        content.append(Paragraph("DESCRIPCIÓN", subtitle_style))
        content.append(Paragraph(activity.descripcion, normal_style))
        content.append(Spacer(1, 0.5*cm))

    # Footer
    content.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey
    )

    content.append(Paragraph(
        f"Documento generado el {timezone.now().strftime('%d de %B de %Y a las %H:%M')}",
        footer_style
    ))

    # Build PDF
    doc.build(content)

    return response

@login_required
@user_passes_test(is_teacher)
def get_filtered_activities(request):
    subject_ids_str = request.GET.get('subject_ids')
    show_context = request.GET.get('show_context') == 'true'
    show_deleted = request.GET.get('show_deleted') == 'true'  # New parameter

    if not subject_ids_str:
        return JsonResponse([], safe=False)

    subject_ids = [int(s_id) for s_id in subject_ids_str.split(',') if s_id.isdigit()]

    final_subject_ids = set(subject_ids)

    if show_context and subject_ids:
        # Find all subjects that share the same course and titulacion
        selected_subjects = Asignatura.objects.filter(id__in=subject_ids)
        titulacion_curso_pairs = selected_subjects.values_list('titulacion_id', 'curso').distinct()

        contextual_subjects = Asignatura.objects.none()
        for titulacion_id, curso in titulacion_curso_pairs:
            contextual_subjects |= Asignatura.objects.filter(titulacion_id=titulacion_id, curso=curso)

        final_subject_ids.update(contextual_subjects.values_list('id', flat=True))

    # Get activities filtered by active/deleted status
    activities_filter = {'asignaturas__id__in': list(final_subject_ids)}
    if show_deleted:
        activities_filter['activa'] = False  # Show only deleted activities
    else:
        activities_filter['activa'] = True   # Show only active activities (default)

    activities = Actividad.objects.filter(**activities_filter).distinct().order_by('fecha_inicio')

    # Manually serialize the data to include related fields
    from django.utils import timezone

    try:
        closing_date = AgendaSettings.load().closing_date
    except Exception:
        closing_date = timezone.now().date()

    activities_data = []
    teacher_subject_ids = set(request.user.subjects.all().values_list('id', flat=True))

    for activity in activities:
        # Get groups for this activity (new system) or use legacy fields
        grupos = activity.grupos.all().order_by('orden')
        
        if grupos.exists():
            # New system: 
            # For multi-group activities: show as single row in table, multiple events in calendar
            # For single-group activities: show normally
            
            if grupos.count() > 1:
                # Multi-group activity: create single entry for table display
                primer_grupo = grupos.first()
                event_class_names = []
                if primer_grupo.fecha_inicio.date() < closing_date:
                    event_class_names.append('past-event')
                else:
                    event_class_names.append('future-event')

                subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])
                
                # Check if the activity belongs to the current teacher
                activity_subject_ids = set(activity.asignaturas.all().values_list('id', flat=True))
                is_own = not teacher_subject_ids.isdisjoint(activity_subject_ids)

                # Create summary info for multi-group activity
                grupos_info = []
                for g in grupos:
                    grupos_info.append({
                        'nombre': g.nombre_grupo,
                        'fecha_inicio': g.fecha_inicio.isoformat(),
                        'fecha_fin': g.fecha_fin.isoformat(),
                        'lugar': g.lugar or '',
                        'descripcion': g.descripcion or ''
                    })

                activities_data.append({
                    'id': activity.id,  # Use activity ID for table display
                    'activity_id': activity.id,
                    'title': f"{activity.nombre} ({grupos.count()} grupos)",
                    'start': primer_grupo.fecha_inicio.isoformat(),
                    'end': primer_grupo.fecha_fin.isoformat(), 
                    'classNames': event_class_names,
                    'extendedProps': {
                        'description': activity.descripcion or primer_grupo.descripcion,
                        'activity_type': activity.tipo_actividad.nombre,
                        'subjects': subject_names,
                        'is_approved': activity.aprobada,
                        'is_active': activity.activa,
                        'evaluable': activity.evaluable,
                        'percentage': activity.porcentaje_evaluacion,
                        'is_own': is_own,
                        'is_multi_group': True,
                        'grupos_count': grupos.count(),
                        'grupos_info': grupos_info
                    }
                })
                
                # Also add individual events for calendar display
                for grupo in grupos:
                    event_class_names = []
                    if grupo.fecha_inicio.date() < closing_date:
                        event_class_names.append('past-event')
                    else:
                        event_class_names.append('future-event')

                    activities_data.append({
                        'id': f"{activity.id}_grupo_{grupo.id}",  # Unique ID for calendar
                        'activity_id': activity.id,
                        'grupo_id': grupo.id,
                        'title': f"{activity.nombre} - Grupo {grupo.nombre_grupo}",
                        'start': grupo.fecha_inicio.isoformat(),
                        'end': grupo.fecha_fin.isoformat(),
                        'classNames': event_class_names + ['calendar-only'],  # Mark as calendar-only
                        'extendedProps': {
                            'description': grupo.descripcion or activity.descripcion,
                            'activity_type': activity.tipo_actividad.nombre,
                            'subjects': subject_names,
                            'is_approved': activity.aprobada,
                            'is_active': activity.activa,
                            'evaluable': activity.evaluable,
                            'percentage': activity.porcentaje_evaluacion,
                            'is_own': is_own,
                            'grupo_nombre': grupo.nombre_grupo,
                            'is_multi_group': True,
                            'is_calendar_event': True  # Mark as calendar-only event
                        }
                    })
            else:
                # Single group activity: show normally
                grupo = grupos.first()
                event_class_names = []
                if grupo.fecha_inicio.date() < closing_date:
                    event_class_names.append('past-event')
                else:
                    event_class_names.append('future-event')

                subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])
                
                # Check if the activity belongs to the current teacher
                activity_subject_ids = set(activity.asignaturas.all().values_list('id', flat=True))
                is_own = not teacher_subject_ids.isdisjoint(activity_subject_ids)

                activities_data.append({
                    'id': activity.id,
                    'activity_id': activity.id,
                    'grupo_id': grupo.id,
                    'title': activity.nombre,
                    'start': grupo.fecha_inicio.isoformat(),
                    'end': grupo.fecha_fin.isoformat(),
                    'classNames': event_class_names,
                    'extendedProps': {
                        'description': grupo.descripcion or activity.descripcion,
                        'activity_type': activity.tipo_actividad.nombre,
                        'subjects': subject_names,
                        'is_approved': activity.aprobada,
                        'is_active': activity.activa,
                        'evaluable': activity.evaluable,
                        'percentage': activity.porcentaje_evaluacion,
                        'is_own': is_own,
                        'is_multi_group': False
                    }
                })
        else:
            # Legacy system: use activity's direct fields
            event_class_names = []
            if activity.fecha_inicio.date() < closing_date:
                event_class_names.append('past-event')
            else:
                event_class_names.append('future-event')

            subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])
            
            # Check if the activity belongs to the current teacher
            activity_subject_ids = set(activity.asignaturas.all().values_list('id', flat=True))
            is_own = not teacher_subject_ids.isdisjoint(activity_subject_ids)

            activities_data.append({
                'id': activity.id,
                'activity_id': activity.id,
                'title': activity.nombre,
                'start': activity.fecha_inicio.isoformat(),
                'end': activity.fecha_fin.isoformat(),
                'classNames': event_class_names,
                'extendedProps': {
                    'description': activity.descripcion,
                    'activity_type': activity.tipo_actividad.nombre,
                    'subjects': subject_names,
                    'is_approved': activity.aprobada,
                    'is_active': activity.activa,
                    'evaluable': activity.evaluable,
                    'percentage': activity.porcentaje_evaluacion,
                    'is_own': is_own,
                    'is_multi_group': False
                }
            })
    
    return JsonResponse(activities_data, safe=False)

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
            tipo_log=_('Reactivation')
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
        activity.set_approval_manually(new_status, modified_by=request.user)
        
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
            return redirect(get_user_dashboard_url(request.user))
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

        activity.set_approval_manually(new_status, modified_by=request.user)

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

    from agenda_academica.models import AgendaSettings
    from django.utils import timezone

    # Load the closing date
    try:
        closing_date = AgendaSettings.load().closing_date
    except Exception:
        # Fallback if AgendaSettings is not configured or an error occurs
        closing_date = timezone.now().date()

    data = []
    for activity in activities.distinct():
        # Get groups for this activity (new system) or use legacy fields
        grupos = activity.grupos.all().order_by('orden')
        
        if grupos.exists():
            # New system: create an event for each group
            for grupo in grupos:
                event_class_names = []
                if grupo.fecha_inicio.date() < closing_date:
                    event_class_names.append('past-event')
                else:
                    event_class_names.append('future-event')

                # Get assigned subject names
                subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])

                # Activity title with group name if multiple groups
                title = activity.nombre
                if grupos.count() > 1:
                    title = f"{activity.nombre} - Grupo {grupo.nombre_grupo}"

                data.append({
                    'id': f"{activity.id}_grupo_{grupo.id}",  # Unique ID for each group
                    'activity_id': activity.id,  # Keep original activity ID for editing
                    'grupo_id': grupo.id,
                    'title': title,
                    'start': grupo.fecha_inicio.isoformat(),
                    'end': grupo.fecha_fin.isoformat(),
                    'classNames': event_class_names,
                    'extendedProps': {
                        'description': grupo.descripcion or activity.descripcion,
                        'activity_type': activity.tipo_actividad.nombre,
                        'subjects': subject_names,
                        'is_approved': activity.aprobada,
                        'is_active': activity.activa,
                        'evaluable': activity.evaluable,
                        'percentage': activity.porcentaje_evaluacion,
                        'grupo_nombre': grupo.nombre_grupo,
                        'is_multi_group': grupos.count() > 1
                    }
                })
        else:
            # Legacy system: use activity's direct fields
            event_class_names = []
            if activity.fecha_inicio.date() < closing_date:
                event_class_names.append('past-event')
            else:
                event_class_names.append('future-event')

            # Get assigned subject names
            subject_names = ", ".join([s.nombre for s in activity.asignaturas.all()])

            data.append({
                'id': activity.id, # Add activity ID for eventClick
                'activity_id': activity.id,
                'title': activity.nombre,
                'start': activity.fecha_inicio.isoformat(),
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
                    'is_multi_group': False
                }
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

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
@require_http_methods(["POST"])
def ajax_create_tipo_actividad(request):
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre', '').strip()
        
        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es requerido'})
        
        if TipoActividad.objects.filter(nombre=nombre).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe un tipo de actividad con ese nombre'})
        
        tipo = TipoActividad.objects.create(nombre=nombre)
        
        # Log the creation
        LogActividad.objects.create(
            object_type='tipo_actividad',
            object_name=tipo.nombre,
            object_id=tipo.id,
            usuario=request.user,
            tipo_log=_('Creation'),
            details=_('Activity type "%(name)s" created') % {'name': tipo.nombre}
        )
        
        return JsonResponse({
            'success': True, 
            'id': tipo.id, 
            'nombre': tipo.nombre
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON inválidos'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
@require_http_methods(["PUT"])
def ajax_update_tipo_actividad(request, pk):
    try:
        tipo = TipoActividad.objects.get(pk=pk)
        data = json.loads(request.body)
        nuevo_nombre = data.get('nombre', '').strip()
        
        if not nuevo_nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es requerido'})
        
        if TipoActividad.objects.filter(nombre=nuevo_nombre).exclude(pk=pk).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe un tipo de actividad con ese nombre'})
        
        old_name = tipo.nombre
        tipo.nombre = nuevo_nombre
        tipo.save()
        
        # Log the update
        LogActividad.objects.create(
            object_type='tipo_actividad',
            object_name=tipo.nombre,
            object_id=tipo.id,
            usuario=request.user,
            tipo_log=_('Modification'),
            details=f'Activity type renamed from "{old_name}" to "{tipo.nombre}"'
        )
        
        return JsonResponse({
            'success': True,
            'id': tipo.id,
            'nombre': tipo.nombre
        })
        
    except TipoActividad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tipo de actividad no encontrado'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON inválidos'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
@require_http_methods(["DELETE"])
def ajax_delete_tipo_actividad(request, pk):
    try:
        tipo = TipoActividad.objects.get(pk=pk)
        data = json.loads(request.body)
        action = data.get('action')
        reassign_to_id = data.get('reassign_to')
        
        # Check if there are activities using this type
        activities_count = Actividad.objects.filter(tipo_actividad=tipo).count()
        
        tipo_name = tipo.nombre  # Store name before deletion
        
        if activities_count > 0 and action == 'reassign' and reassign_to_id:
            try:
                reassign_to_type = TipoActividad.objects.get(pk=reassign_to_id)
                with transaction.atomic():
                    # Reassign activities
                    Actividad.objects.filter(tipo_actividad=tipo).update(tipo_actividad=reassign_to_type)
                    # Then delete the TipoActividad
                    tipo.delete()
                    
                    # Log the deletion with reassignment
                    LogActividad.objects.create(
                        object_type='tipo_actividad',
                        object_name=tipo_name,
                        object_id=pk,
                        usuario=request.user,
                        tipo_log=_('Deletion'),
                        details=f'Activity type "{tipo_name}" deleted. {activities_count} activities reassigned to "{reassign_to_type.nombre}"'
                    )
                    
                return JsonResponse({'success': True})
            except TipoActividad.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Tipo de actividad de destino no válido'})
        elif activities_count > 0 and action == 'cascade':
            # Perform cascade delete
            tipo.delete()
            
            # Log the cascade deletion
            LogActividad.objects.create(
                object_type='tipo_actividad',
                object_name=tipo_name,
                object_id=pk,
                usuario=request.user,
                tipo_log='Eliminación',
                details=f'Activity type "{tipo_name}" deleted with cascade. {activities_count} activities also deleted'
            )
            
            return JsonResponse({'success': True})
        elif activities_count == 0:
            # No activities, safe to delete
            tipo.delete()
            
            # Log the simple deletion
            LogActividad.objects.create(
                object_type='tipo_actividad',
                object_name=tipo_name,
                object_id=pk,
                usuario=request.user,
                tipo_log='Eliminación',
                details=f'Activity type "{tipo_name}" deleted (no associated activities)'
            )
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Acción no válida'})
            
    except TipoActividad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tipo de actividad no encontrado'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON inválidos'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
def ajax_get_activity_count(request, pk):
    try:
        tipo = TipoActividad.objects.get(pk=pk)
        activities_count = Actividad.objects.filter(tipo_actividad=tipo).count()
        other_types = TipoActividad.objects.exclude(pk=pk).values('id', 'nombre')
        
        return JsonResponse({
            'success': True,
            'activities_count': activities_count,
            'other_types': list(other_types)
        })
        
    except TipoActividad.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tipo de actividad no encontrado'})

# ==================== ACTIVITY VERSIONING VIEWS ====================

@login_required 
@user_passes_test(is_teacher)
def activity_version_history(request, pk):
    """Show version history for an activity"""
    activity = get_object_or_404(Actividad, pk=pk)
    
    # Check if user has permission to view this activity
    # Teachers can view activities for their assigned subjects
    user_subjects = request.user.subjects.all()
    activity_subjects = activity.asignaturas.all()
    
    # Check if user has at least one subject in common with the activity
    has_permission = any(subject in user_subjects for subject in activity_subjects)
    
    if not has_permission and request.user.role not in ['ADMIN', 'COORDINATOR']:
        return HttpResponseRedirect(reverse_lazy(get_user_dashboard_url(request.user)))
    
    # Get all versions of this activity, ordered by version number (newest first)
    versions = ActividadVersion.objects.filter(actividad_original=activity).order_by('-version_numero')
    
    return render(request, 'schedule/activity_version_history.html', {
        'activity': activity,
        'versions': versions,
    })

@login_required
@user_passes_test(is_teacher) 
def activity_version_detail(request, pk, version_id):
    """Show details of a specific version"""
    activity = get_object_or_404(Actividad, pk=pk)
    version = get_object_or_404(ActividadVersion, pk=version_id, actividad_original=activity)
    
    # Same permission check as version history
    user_subjects = request.user.subjects.all()
    activity_subjects = activity.asignaturas.all()
    has_permission = any(subject in user_subjects for subject in activity_subjects)
    
    if not has_permission and request.user.role not in ['ADMIN', 'COORDINATOR']:
        return HttpResponseRedirect(reverse_lazy(get_user_dashboard_url(request.user)))
    
    return render(request, 'schedule/activity_version_detail.html', {
        'activity': activity,
        'version': version,
    })

@login_required
@user_passes_test(is_teacher)
def activity_restore_version(request, pk, version_id):
    """Restore an activity to a previous version"""
    activity = get_object_or_404(Actividad, pk=pk)
    version = get_object_or_404(ActividadVersion, pk=version_id, actividad_original=activity)
    
    # Same permission check
    user_subjects = request.user.subjects.all()
    activity_subjects = activity.asignaturas.all()
    has_permission = any(subject in user_subjects for subject in activity_subjects)
    
    if not has_permission and request.user.role not in ['ADMIN', 'COORDINATOR']:
        return HttpResponseRedirect(reverse_lazy(get_user_dashboard_url(request.user)))
    
    if request.method == 'POST':
        # Set version metadata before restoring
        activity._modified_by = request.user
        activity._version_comment = f'Restored to version {version.version_numero} from {version.fecha_modificacion.strftime("%Y-%m-%d %H:%M")}'
        
        # Restore all fields from the version
        activity.nombre = version.nombre
        activity.descripcion = version.descripcion
        activity.fecha_inicio = version.fecha_inicio
        activity.fecha_fin = version.fecha_fin
        activity.evaluable = version.evaluable
        activity.porcentaje_evaluacion = version.porcentaje_evaluacion
        activity.no_recuperable = version.no_recuperable
        activity.aprobada = version.aprobada
        activity.activa = version.activa
        
        activity.save()
        
        # Restore asignaturas relationships
        activity.asignaturas.clear()
        if version.asignaturas_snapshot:
            asignatura_ids = [asig['id'] for asig in version.asignaturas_snapshot]
            asignaturas = Asignatura.objects.filter(id__in=asignatura_ids)
            activity.asignaturas.set(asignaturas)
        
        # Restore tipo_actividad if available
        if version.tipo_actividad_snapshot and version.tipo_actividad_snapshot.get('id'):
            try:
                tipo_actividad = TipoActividad.objects.get(id=version.tipo_actividad_snapshot['id'])
                activity.tipo_actividad = tipo_actividad
                activity.save()
            except TipoActividad.DoesNotExist:
                pass  # If the tipo_actividad no longer exists, keep current one
        
        # Log the restoration
        LogActividad.objects.create(
            object_type='actividad',
            object_name=activity.nombre,
            object_id=activity.id,
            actividad=activity,
            usuario=request.user,
            tipo_log=_('Version Restore'),
            details=f'Activity restored to version {version.version_numero} from {version.fecha_modificacion.strftime("%Y-%m-%d %H:%M")}'
        )
        
        return redirect('activity_version_history', pk=activity.pk)
    
    return render(request, 'schedule/activity_restore_confirm.html', {
        'activity': activity,
        'version': version,
    })

# ==================== PDF REPORTS VIEWS ====================

@login_required
@user_passes_test(is_coordinator_or_admin)
def generate_agenda_report(request, titulacion_id=None):
    """Generate PDF agenda report for coordinators (specific titulacion) or admins (all titulaciones)"""
    
    if not REPORTLAB_AVAILABLE:
        return HttpResponse("PDF generation is not available. Please install reportlab.", status=500)
    
    # Check permissions and get data
    if request.user.role == 'COORDINATOR':
        # Coordinators can only generate reports for their coordinated titulaciones
        if titulacion_id:
            titulacion = get_object_or_404(Titulacion, pk=titulacion_id)
            user_coordinated_titulaciones = Titulacion.objects.filter(coordinador=request.user)
            if titulacion not in user_coordinated_titulaciones:
                return HttpResponse("You don't have permission to generate reports for this titulacion.", status=403)
            titulaciones = [titulacion]
        else:
            # If no specific titulacion, get all coordinated titulaciones
            titulaciones = Titulacion.objects.filter(coordinador=request.user)
    else:  # ADMIN
        if titulacion_id:
            titulaciones = [get_object_or_404(Titulacion, pk=titulacion_id)]
        else:
            titulaciones = Titulacion.objects.all()
    
    if not titulaciones:
        return HttpResponse("No titulaciones found for report generation.", status=404)
    
    # Create response
    response = HttpResponse(content_type='application/pdf')
    if len(titulaciones) == 1:
        filename = f"Agenda_{titulaciones[0].nombre.replace(' ', '_')}.pdf"
    else:
        filename = "Agenda_General_Centro.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.HexColor('#2c3e50'),
        alignment=1  # Center
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=12,
        textColor=colors.HexColor('#34495e')
    )
    
    course_style = ParagraphStyle(
        'CourseHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#7f8c8d')
    )
    
    for titulacion_idx, titulacion in enumerate(titulaciones):
        # Add title
        if len(titulaciones) == 1:
            title = f"Agenda de {titulacion.nombre}"
        else:
            title = f"Agenda General del Centro"
            if titulacion_idx == 0:
                elements.append(Paragraph(title, title_style))
                elements.append(Spacer(1, 20))
        
        if len(titulaciones) > 1:
            elements.append(Paragraph(f"Titulación: {titulacion.nombre}", heading_style))
        elif titulacion_idx == 0:
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 20))
        
        # Get activities for this titulacion (only active ones)
        activities = Actividad.objects.filter(
            asignaturas__titulacion=titulacion,
            activa=True
        ).select_related('tipo_actividad').prefetch_related('asignaturas').distinct().order_by('fecha_inicio')
        
        if not activities.exists():
            elements.append(Paragraph("No hay actividades activas para esta titulación.", styles['Normal']))
            continue
        
        # Group activities by course
        courses_data = {}
        for activity in activities:
            for asignatura in activity.asignaturas.filter(titulacion=titulacion):
                course = asignatura.curso
                course_name = "Optativa" if course == 10 else "TFE" if course == 1000 else str(course)
                
                if course not in courses_data:
                    courses_data[course] = {
                        'name': course_name,
                        'activities': []
                    }
                
                # Avoid duplicates
                if activity not in courses_data[course]['activities']:
                    courses_data[course]['activities'].append(activity)
        
        # Sort courses
        sorted_courses = sorted(courses_data.items(), key=lambda x: x[0] if x[0] not in [10, 1000] else (999 if x[0] == 10 else 1001))
        
        for course_num, course_data in sorted_courses:
            elements.append(Paragraph(f"Curso {course_data['name']}", course_style))
            
            # Create table data with proper text wrapping
            table_data = [['Actividad', 'Asignatura', 'Tipo', 'Inicio', 'Fin', 'Evaluable']]
            
            # Create paragraph style for table content
            cell_style = ParagraphStyle(
                'TableCell',
                parent=styles['Normal'],
                fontSize=8,
                leading=10,
                alignment=0,  # Left alignment
                spaceAfter=0
            )
            
            for activity in sorted(course_data['activities'], key=lambda x: x.fecha_inicio):
                # Get subject names for this course
                subject_names = ", ".join([
                    asig.nombre for asig in activity.asignaturas.filter(titulacion=titulacion, curso=course_num)
                ])
                
                evaluable = "Sí" if activity.evaluable else "No"
                if activity.evaluable and activity.porcentaje_evaluacion:
                    evaluable += f" ({activity.porcentaje_evaluacion}%)"
                
                # Create paragraphs for text content to handle wrapping
                table_data.append([
                    Paragraph(activity.nombre, cell_style),
                    Paragraph(subject_names, cell_style),
                    Paragraph(activity.tipo_actividad.nombre, cell_style),
                    Paragraph(activity.fecha_inicio.strftime('%d/%m/%Y<br/>%H:%M'), cell_style),
                    Paragraph(activity.fecha_fin.strftime('%d/%m/%Y<br/>%H:%M'), cell_style),
                    Paragraph(evaluable, cell_style)
                ])
            
            # Create table with adjusted column widths
            table = Table(table_data, colWidths=[2.2*inch, 1.8*inch, 1.2*inch, 0.9*inch, 0.9*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Header centered
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),   # Content left-aligned
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Top alignment for better readability
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        # Add page break between titulaciones if multiple
        if len(titulaciones) > 1 and titulacion_idx < len(titulaciones) - 1:
            elements.append(PageBreak())
    
    # Add footer with generation info
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {request.user.username}", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Log the action
    LogActividad.objects.create(
        object_type='actividad',
        object_name=f"PDF Report: {filename}",
        usuario=request.user,
        tipo_log=_('Report Generation'),
        details=f'PDF agenda report generated for {len(titulaciones)} titulacion(s)'
    )
    
    return response

@login_required
@user_passes_test(is_coordinator_or_admin)
def create_automatic_icals(request):
    """Create automatic iCal feeds for all courses and titulaciones"""
    created_feeds = []
    existing_feeds = []
    
    # Get titulaciones based on user role
    if request.user.role == 'COORDINATOR':
        titulaciones = Titulacion.objects.filter(coordinador=request.user)
    else:  # ADMIN
        titulaciones = Titulacion.objects.all()
    
    for titulacion in titulaciones:
        # 1. Create iCal for the entire titulacion
        titulacion_name = f"Agenda completa - {titulacion.nombre}"
        existing_titulacion_feed = VistaCalendario.objects.filter(
            usuario=request.user,
            nombre=titulacion_name
        ).first()
        
        if not existing_titulacion_feed:
            # Create new feed for entire titulacion
            titulacion_feed = VistaCalendario.objects.create(
                usuario=request.user,
                nombre=titulacion_name,
                token=str(uuid.uuid4())
            )
            # Add all subjects from this titulacion
            titulacion_subjects = Asignatura.objects.filter(titulacion=titulacion)
            titulacion_feed.asignaturas.set(titulacion_subjects)
            created_feeds.append(titulacion_name)
        else:
            existing_feeds.append(titulacion_name)
        
        # 2. Create iCal for each course within the titulacion
        courses = Asignatura.objects.filter(titulacion=titulacion).values_list('curso', flat=True).distinct()
        
        for course in courses:
            # Get human-readable course name
            if course == 10:
                course_display = "Optativa"
            elif course == 1000:
                course_display = "TFE"
            else:
                course_display = str(course)
            
            course_name = f"{titulacion.nombre} - Curso {course_display}"
            existing_course_feed = VistaCalendario.objects.filter(
                usuario=request.user,
                nombre=course_name
            ).first()
            
            if not existing_course_feed:
                # Create new feed for this course
                course_feed = VistaCalendario.objects.create(
                    usuario=request.user,
                    nombre=course_name,
                    token=str(uuid.uuid4())
                )
                # Add subjects from this course
                course_subjects = Asignatura.objects.filter(titulacion=titulacion, curso=course)
                course_feed.asignaturas.set(course_subjects)
                created_feeds.append(course_name)
            else:
                existing_feeds.append(course_name)
    
    # Log the action
    LogActividad.objects.create(
        object_type='actividad',
        object_name="Automatic iCal Creation",
        usuario=request.user,
        tipo_log=_('iCal Generation'),
        details=f'Created {len(created_feeds)} new iCal feeds, {len(existing_feeds)} already existed'
    )
    
    return JsonResponse({
        'success': True,
        'created': len(created_feeds),
        'existing': len(existing_feeds),
        'created_feeds': created_feeds,
        'existing_feeds': existing_feeds
    })

@login_required
@user_passes_test(is_coordinator_or_admin)
def ical_management(request):
    """iCal management page with all feeds and copy links"""
    
    # Get all calendar views for this user, ordered by name
    calendar_views = VistaCalendario.objects.filter(usuario=request.user).order_by('nombre')
    
    # Group by type (complete titulacion vs course-specific)
    complete_feeds = []
    course_feeds = []
    manual_feeds = []
    
    for feed in calendar_views:
        if "Agenda completa -" in feed.nombre:
            complete_feeds.append(feed)
        elif " - Curso " in feed.nombre:
            course_feeds.append(feed)
        else:
            manual_feeds.append(feed)
    
    context = {
        'complete_feeds': complete_feeds,
        'course_feeds': course_feeds,
        'manual_feeds': manual_feeds,
        'base_url': request.build_absolute_uri('/')[:-1]  # Remove trailing slash
    }
    
    return render(request, 'schedule/ical_management.html', context)

@login_required
@user_passes_test(is_coordinator_or_admin)
@require_POST
def delete_all_icals(request):
    """Delete all iCal feeds for the current user"""
    
    feeds = VistaCalendario.objects.filter(usuario=request.user)
    count = feeds.count()
    feeds.delete()
    
    # Log the action
    LogActividad.objects.create(
        object_type='actividad',
        object_name="Delete All iCals",
        usuario=request.user,
        tipo_log=_('iCal Deletion'),
        details=f'Deleted {count} iCal feeds for user {request.user.username}'
    )
    
    return JsonResponse({'success': True, 'deleted_count': count})

from django.utils import timezone # Need this for date comparison

@login_required
@user_passes_test(is_teacher)
def check_and_edit_activity(request, pk):
    """
    Intermediate view to check if an activity is a "contract" activity
    before allowing an edit or forcing a copy.
    """
    activity = get_object_or_404(Actividad, pk=pk)
    
    # IDOR check
    if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
        return redirect(get_user_dashboard_url(request.user))

    try:
        lock_date = AgendaSettings.load().closing_date
        creation_log = LogActividad.objects.filter(actividad=activity, tipo_log='Creation').order_by('timestamp').first()
        
        is_contract_activity = creation_log and creation_log.timestamp.date() < lock_date
        is_after_lock_date = timezone.now().date() >= lock_date

        # The special copy logic is triggered only when editing a contract activity after the lock date
        if is_contract_activity and is_after_lock_date:
            if request.method == 'POST':
                # User confirmed, let's create the copy
                
                # 1. Create a new activity instance in memory
                new_activity = activity
                new_activity.pk = None # This is the key to creating a new object
                new_activity.id = None

                # 2. Modify the name as requested
                new_activity.nombre = f"{activity.nombre} [Modificación de actividad inicial]"
                
                # 3. Save the new base object
                new_activity.save()

                # 4. Copy the ManyToMany relationship
                new_activity.asignaturas.set(activity.asignaturas.all())

                # 5. Create a log entry for the copy action
                LogActividad.objects.create(
                    object_type='actividad',
                    object_name=new_activity.nombre,
                    object_id=new_activity.id,
                    actividad=new_activity,
                    usuario=request.user,
                    tipo_log='Copia',
                    details=f'Copia creada desde la actividad de contrato ID {activity.pk}: "{activity.nombre}"'
                )

                # 6. Redirect to the edit form of the NEW activity
                return redirect('activity_edit', pk=new_activity.pk)
            
            # On GET, show the confirmation page
            return render(request, 'schedule/activity_confirm_copy.html', {'activity': activity})

    except (AgendaSettings.DoesNotExist, LogActividad.DoesNotExist):
        # If settings or log don't exist, fail safe and proceed to normal edit
        pass

    # If any condition fails or an exception occurs, proceed to the normal edit form
    return redirect('activity_edit', pk=activity.pk)

@login_required
@user_passes_test(is_teacher)
def multi_group_activity_form(request, grupo_id=None):
    initial_groups = []
    existing_activities = Actividad.objects.none()  # Initialize as empty QuerySet
    
    if grupo_id:
        existing_activities = Actividad.objects.filter(grupo_id=grupo_id, activa=True)
        if existing_activities.exists():
            first_activity = existing_activities.first()
            initial_groups = []
            for activity in existing_activities:
                initial_groups.append({
                    'grupo': activity.descripcion.split(':')[0].replace('Grupo ', '') if ':' in activity.descripcion else '',
                    'fecha_inicio': activity.fecha_inicio.isoformat(),
                    'fecha_fin': activity.fecha_fin.isoformat(),
                    'descripcion': activity.descripcion.split(':', 1)[1].strip() if ':' in activity.descripcion else activity.descripcion
                })

    if request.method == 'POST':
        form = MultiGroupActivityForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if grupo_id:
                        existing_activities.update(activa=False)
                        for activity in existing_activities:
                            LogActividad.objects.create(
                                object_type='actividad',
                                object_name=activity.nombre,
                                object_id=activity.id,
                                actividad=activity,
                                usuario=request.user,
                                tipo_log=_('Modification'),
                                details=_('Multi-group activity updated - old version deactivated')
                            )
                    
                    actividades_creadas = form.save(user=request.user)
                    
                    for activity in actividades_creadas:
                        LogActividad.objects.create(
                            object_type='actividad',
                            object_name=activity.nombre,
                            object_id=activity.id,
                            actividad=activity,
                            usuario=request.user,
                            tipo_log=_('Creation') if not grupo_id else _('Modification'),
                            details=_('Multi-group activity created/updated')
                        )
                    
                    return redirect(get_user_dashboard_url(request.user))
            except Exception as e:
                form.add_error(None, f"Error al guardar: {str(e)}")
    else:
        initial_data = {}
        if existing_activities.exists():
            first_activity = existing_activities.first()
            initial_data = {
                'nombre': first_activity.nombre,
                'asignaturas': first_activity.asignaturas.all(),
                'tipo_actividad': first_activity.tipo_actividad,
                'evaluable': first_activity.evaluable,
                'porcentaje_evaluacion': first_activity.porcentaje_evaluacion,
                'no_recuperable': first_activity.no_recuperable,
            }
        else:
            # Handle pre-selected subjects from URL parameter
            subjects_param = request.GET.get('subjects')
            if subjects_param:
                try:
                    subject_ids = [int(id) for id in subjects_param.split(',')]
                    pre_selected_subjects = request.user.subjects.filter(id__in=subject_ids)
                    initial_data['asignaturas'] = pre_selected_subjects
                except (ValueError, TypeError):
                    pass  # Ignore invalid subject IDs
        
        form = MultiGroupActivityForm(initial=initial_data, user=request.user, initial_groups=initial_groups)

    return render(request, 'schedule/multi_group_activity_form.html', {
        'form': form, 
        'grupo_id': grupo_id,
        'is_edit': bool(grupo_id)
    })

@login_required
@user_passes_test(is_teacher)
def copy_activity_individual(request, activity_id):
    """Copy an existing activity as an individual activity using the unified system"""
    original_activity = get_object_or_404(Actividad, pk=activity_id)
    
    # Check if user can access this activity (must be in their subjects)
    user_subjects = request.user.subjects.all()
    if not original_activity.asignaturas.filter(id__in=user_subjects.values_list('id', flat=True)).exists():
        return HttpResponseRedirect(get_user_dashboard_url(request.user))
    
    if request.method == 'POST':
        form = UnifiedActivityForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    activity = form.save(user=request.user)
                    
                    # Log the activity creation
                    LogActividad.objects.create(
                        object_type='actividad',
                        object_name=activity.nombre,
                        object_id=activity.id,
                        actividad=activity,
                        usuario=request.user,
                        tipo_log='Creation',
                        details=f'Activity copied from "{original_activity.nombre}"'
                    )
                    
                    return redirect(get_user_dashboard_url(request.user))
            except Exception as e:
                print(f"Error copying activity: {e}")
                form.add_error(None, f"Error al copiar la actividad: {str(e)}")
    else:
        # Prepare initial data from the original activity
        initial_data = {
            'nombre': f"Copia de {original_activity.nombre}",
            'asignaturas': original_activity.asignaturas.all(),
            'tipo_actividad': original_activity.tipo_actividad,
            'evaluable': original_activity.evaluable,
            'porcentaje_evaluacion': original_activity.porcentaje_evaluacion,
            'no_recuperable': original_activity.no_recuperable,
        }
        
        # Create single group data from original activity
        grupos_data = []
        if hasattr(original_activity, 'grupos') and original_activity.grupos.exists():
            # Use first group from multi-group activity
            primer_grupo = original_activity.grupos.first()
            grupos_data.append({
                'grupo': 'Principal',
                'fecha_inicio': primer_grupo.fecha_inicio.strftime('%Y-%m-%dT%H:%M'),
                'fecha_fin': primer_grupo.fecha_fin.strftime('%Y-%m-%dT%H:%M'),
                'lugar': primer_grupo.lugar or '',
                'descripcion': primer_grupo.descripcion or original_activity.descripcion or '',
            })
        else:
            # Use legacy activity data
            grupos_data.append({
                'grupo': 'Principal',
                'fecha_inicio': original_activity.fecha_inicio.strftime('%Y-%m-%dT%H:%M'),
                'fecha_fin': original_activity.fecha_fin.strftime('%Y-%m-%dT%H:%M'),
                'lugar': '',
                'descripcion': original_activity.descripcion or '',
            })
        
        # Create form with pre-filled data
        form = UnifiedActivityForm(initial=initial_data, user=request.user, initial_groups=grupos_data)
    
    return render(request, 'schedule/unified_activity_form.html', {
        'form': form,
        'is_copy': True,
        'original_activity': original_activity
    })

@login_required
@user_passes_test(is_teacher)
def copy_activity_multi_group(request, activity_id):
    """Copy an existing activity as a multi-group activity using the unified system"""
    original_activity = get_object_or_404(Actividad, pk=activity_id)
    
    # Check if user can access this activity
    user_subjects = request.user.subjects.all()
    if not original_activity.asignaturas.filter(id__in=user_subjects.values_list('id', flat=True)).exists():
        return HttpResponseRedirect(get_user_dashboard_url(request.user))
    
    if request.method == 'POST':
        form = UnifiedActivityForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    activity = form.save(user=request.user)
                    
                    # Log the activity creation
                    LogActividad.objects.create(
                        object_type='actividad',
                        object_name=activity.nombre,
                        object_id=activity.id,
                        actividad=activity,
                        usuario=request.user,
                        tipo_log='Creation',
                        details=f'Multi-group activity copied from "{original_activity.nombre}"'
                    )
                    
                    return redirect(get_user_dashboard_url(request.user))
            except Exception as e:
                print(f"Error copying activity: {e}")
                form.add_error(None, f"Error al copiar la actividad: {str(e)}")
    else:
        # Prepare initial data
        initial_data = {
            'nombre': f"Copia de {original_activity.nombre}",
            'asignaturas': original_activity.asignaturas.all(),
            'tipo_actividad': original_activity.tipo_actividad,
            'evaluable': original_activity.evaluable,
            'porcentaje_evaluacion': original_activity.porcentaje_evaluacion,
            'no_recuperable': original_activity.no_recuperable,
        }
        
        # Copy group structure if original activity has groups
        grupos_data = []
        if hasattr(original_activity, 'grupos') and original_activity.grupos.exists():
            for grupo in original_activity.grupos.all():
                grupos_data.append({
                    'grupo': grupo.nombre_grupo,
                    'fecha_inicio': grupo.fecha_inicio.strftime('%Y-%m-%dT%H:%M') if grupo.fecha_inicio else '',
                    'fecha_fin': grupo.fecha_fin.strftime('%Y-%m-%dT%H:%M') if grupo.fecha_fin else '',
                    'lugar': grupo.lugar or '',
                    'descripcion': grupo.descripcion or '',
                })
        else:
            # If no groups exist, create two from main activity data for multi-group
            grupos_data.append({
                'grupo': '1',
                'fecha_inicio': original_activity.fecha_inicio.strftime('%Y-%m-%dT%H:%M') if original_activity.fecha_inicio else '',
                'fecha_fin': original_activity.fecha_fin.strftime('%Y-%m-%dT%H:%M') if original_activity.fecha_fin else '',
                'lugar': '',
                'descripcion': original_activity.descripcion or '',
            })
            grupos_data.append({
                'grupo': '2',
                'fecha_inicio': original_activity.fecha_inicio.strftime('%Y-%m-%dT%H:%M') if original_activity.fecha_inicio else '',
                'fecha_fin': original_activity.fecha_fin.strftime('%Y-%m-%dT%H:%M') if original_activity.fecha_fin else '',
                'lugar': '',
                'descripcion': original_activity.descripcion or '',
            })
        
        # Create form with pre-filled data
        form = UnifiedActivityForm(initial=initial_data, user=request.user, initial_groups=grupos_data)
    
    return render(request, 'schedule/unified_activity_form.html', {
        'form': form,
        'is_copy': True,
        'original_activity': original_activity
    })

@login_required
@user_passes_test(is_teacher)
def unified_activity_form(request, pk=None):
    """
    Vista unificada para crear/editar actividades individuales o multi-grupo
    usando el nuevo modelo ActividadGrupo
    """
    activity = None
    initial_groups = []
    
    if pk:
        # Modo edición
        activity = get_object_or_404(Actividad, pk=pk)
        
        # IDOR check
        if not request.user.is_staff and not activity.asignaturas.filter(id__in=request.user.subjects.all()).exists():
            return redirect(get_user_dashboard_url(request.user))
            
        # Cargar grupos existentes
        grupos = activity.grupos.all().order_by('orden')
        for grupo in grupos:
            initial_groups.append({
                'grupo': grupo.nombre_grupo,
                'fecha_inicio': grupo.fecha_inicio.strftime('%Y-%m-%dT%H:%M'),
                'fecha_fin': grupo.fecha_fin.strftime('%Y-%m-%dT%H:%M'),
                'descripcion': grupo.descripcion or '',
                'lugar': grupo.lugar or ''
            })
    else:
        # Modo creación - verificar si hay asignaturas preseleccionadas
        subject_ids_str = request.GET.get('subjects')
        if subject_ids_str:
            try:
                subject_ids = [int(s_id) for s_id in subject_ids_str.split(',') if s_id.isdigit()]
                # Validar que las asignaturas pertenecen al usuario
                user_subject_ids = set(request.user.subjects.all().values_list('id', flat=True))
                valid_subject_ids = [sid for sid in subject_ids if sid in user_subject_ids]
                if valid_subject_ids:
                    initial_subjects = Asignatura.objects.filter(id__in=valid_subject_ids)
                else:
                    initial_subjects = []
            except (ValueError, TypeError):
                initial_subjects = []
        else:
            initial_subjects = []

    if request.method == 'POST':
        form = UnifiedActivityForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if activity:
                        # Modo edición - actualizar actividad existente
                        activity.nombre = form.cleaned_data['nombre']
                        activity.tipo_actividad = form.cleaned_data['tipo_actividad']
                        activity.evaluable = form.cleaned_data['evaluable']
                        activity.porcentaje_evaluacion = form.cleaned_data['porcentaje_evaluacion']
                        activity.no_recuperable = form.cleaned_data['no_recuperable']
                        
                        # Actualizar campos temporales de compatibilidad
                        grupos_data = form.cleaned_data['grupos_data']
                        if grupos_data:
                            activity.fecha_inicio = grupos_data[0]['fecha_inicio']
                            activity.fecha_fin = grupos_data[0]['fecha_fin']
                            activity.descripcion = grupos_data[0].get('descripcion', '')
                        
                        activity.save()
                        activity.asignaturas.set(form.cleaned_data['asignaturas'])
                        
                        # Eliminar grupos existentes y crear nuevos
                        activity.grupos.all().delete()
                        for i, grupo_info in enumerate(grupos_data, 1):
                            ActividadGrupo.objects.create(
                                actividad=activity,
                                nombre_grupo=grupo_info['grupo'],
                                fecha_inicio=grupo_info['fecha_inicio'],
                                fecha_fin=grupo_info['fecha_fin'],
                                descripcion=grupo_info.get('descripcion', ''),
                                lugar=grupo_info.get('lugar', ''),
                                orden=i
                            )
                        
                        # Log de modificación
                        LogActividad.objects.create(
                            object_type='actividad',
                            object_name=activity.nombre,
                            object_id=activity.id,
                            actividad=activity,
                            usuario=request.user,
                            tipo_log=_('Modification'),
                            details=f'Actividad actualizada con {len(grupos_data)} grupo(s) usando nuevo sistema'
                        )
                    else:
                        # Modo creación - crear nueva actividad
                        activity = form.save(user=request.user)
                        
                        # Log de creación
                        LogActividad.objects.create(
                            object_type='actividad',
                            object_name=activity.nombre,
                            object_id=activity.id,
                            actividad=activity,
                            usuario=request.user,
                            tipo_log=_('Creation'),
                            details=f'Actividad creada con {activity.grupos.count()} grupo(s) usando nuevo sistema'
                        )
                    
                    return redirect(get_user_dashboard_url(request.user))
                    
            except Exception as e:
                form.add_error(None, f"Error al guardar: {str(e)}")
    else:
        # GET request
        if activity:
            # Preparar datos iniciales para edición
            initial_data = {
                'nombre': activity.nombre,
                'asignaturas': activity.asignaturas.all(),
                'tipo_actividad': activity.tipo_actividad,
                'evaluable': activity.evaluable,
                'porcentaje_evaluacion': activity.porcentaje_evaluacion,
                'no_recuperable': activity.no_recuperable,
            }
        else:
            # Preparar datos iniciales para creación
            initial_data = {}
            if 'initial_subjects' in locals() and initial_subjects:
                initial_data['asignaturas'] = initial_subjects
        
        form = UnifiedActivityForm(initial=initial_data, user=request.user, initial_groups=initial_groups)

    return render(request, 'schedule/unified_activity_form.html', {
        'form': form,
        'activity': activity,
        'is_edit': bool(pk)
    })