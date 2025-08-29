from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('teacher_dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student_dashboard/', views.student_dashboard, name='student_dashboard'),
    path('select_subjects/', views.select_subjects, name='select_subjects'),
    path('ical_config/', views.student_ical_config, name='student_ical_config'),
    path('teacher_select_subjects/', views.teacher_select_subjects, name='teacher_select_subjects'),
    path('teacher_student_view/', views.teacher_student_view, name='teacher_student_view'),
    path('coordinator_dashboard/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('send_notification/', views.send_notification, name='send_notification'),
    path('kpi_report/', views.kpi_report, name='kpi_report'),
    path('assign_coordinators/', views.assign_coordinators, name='assign_coordinators'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard_redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('api/student_events/', views.student_calendar_events, name='student_calendar_events'),
    path('ajax/coordinator/update/', views.ajax_update_coordinator, name='ajax_update_coordinator'),
]
