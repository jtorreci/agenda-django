from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
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
    path('login_attempts/', views.login_attempts, name='login_attempts'),
    # Tipos de Perfil AJAX endpoints
    path('ajax/tipo-perfil/create/', views.ajax_create_tipo_perfil, name='ajax_create_tipo_perfil'),
    path('ajax/tipo-perfil/<int:pk>/update/', views.ajax_update_tipo_perfil, name='ajax_update_tipo_perfil'),
    path('ajax/tipo-perfil/<int:pk>/delete/', views.ajax_delete_tipo_perfil, name='ajax_delete_tipo_perfil'),
]
