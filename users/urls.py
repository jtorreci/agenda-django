from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('teacher_dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student_dashboard/', views.student_dashboard, name='student_dashboard'),
    path('select_subjects/', views.select_subjects, name='select_subjects'),
    path('teacher_select_subjects/', views.teacher_select_subjects, name='teacher_select_subjects'),
    path('teacher_student_view/', views.teacher_student_view, name='teacher_student_view'),
    path('coordinator_dashboard/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('send_notification/', views.send_notification, name='send_notification'),
    path('kpi_report/', views.kpi_report, name='kpi_report'),
    path('dashboard_redirect/', views.dashboard_redirect, name='dashboard_redirect'),
]
