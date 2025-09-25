"""
URL configuration for agenda_academica project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from schedule import views as schedule_views
from agenda_academica import views as agenda_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='logout_success'), name='logout'),
    path('logout_success/', agenda_views.logout_success, name='logout_success'),
    path('ajax/get_cursos/', schedule_views.get_cursos, name='get_cursos'),
    path('ajax/get_semestres/', schedule_views.get_semestres, name='get_semestres'),
    path('ajax/get_asignaturas/', schedule_views.get_asignaturas, name='get_asignaturas'),
    path('ajax/get_filtered_activities/', schedule_views.get_filtered_activities, name='get_filtered_activities'),
    path('ajax/get_filtered_asignaturas/', schedule_views.get_filtered_asignaturas, name='get_filtered_asignaturas'),
    path('activity/new/', schedule_views.activity_form, name='activity_new'),
    path('activity/unified/new/', schedule_views.unified_activity_form, name='unified_activity_new'),
    path('activity/unified/edit/<int:pk>/', schedule_views.unified_activity_form, name='unified_activity_edit'),
    path('activity/multi-group/new/', schedule_views.multi_group_activity_form, name='multi_group_activity_new'),
    path('activity/multi-group/edit/<uuid:grupo_id>/', schedule_views.multi_group_activity_form, name='multi_group_activity_edit'),
    # Copy activities
    path('activity/copy/<int:activity_id>/individual/', schedule_views.copy_activity_individual, name='copy_activity_individual'),
    path('activity/copy/<int:activity_id>/multi-group/', schedule_views.copy_activity_multi_group, name='copy_activity_multi_group'),
    path('activity/edit/<int:pk>/', schedule_views.activity_form, name='activity_edit'),
    path('activity/check-edit/<int:pk>/', schedule_views.check_and_edit_activity, name='activity_check_edit'),
    path('activity/details/<int:pk>/', schedule_views.activity_form, {'read_only': True}, name='activity_details_readonly'),
    path('activity/view/<int:pk>/', schedule_views.activity_detail_view, name='activity_detail_view'),
    path('activity/pdf/<int:pk>/', schedule_views.activity_pdf_convocatoria, name='activity_pdf_convocatoria'),
    path('activity/delete/<int:pk>/', schedule_views.activity_delete, name='activity_delete'),
    path('activity/list/', schedule_views.activity_list, name='activity_list'),
    path('activity/logs/', schedule_views.activity_logs, name='activity_logs'),
    path('activity/reactivate/<int:pk>/', schedule_views.reactivate_activity, name='reactivate_activity'),
    path('activity/toggle_approval/<int:pk>/', schedule_views.toggle_activity_approval, name='toggle_activity_approval'),
    path('calendar_views/', schedule_views.calendar_view_panel, name='calendar_view_panel'),
    path('calendar_views/new/', schedule_views.create_calendar_view, name='create_calendar_view'),
    path('calendar_views/delete/<int:pk>/', schedule_views.delete_calendar_view, name='delete_calendar_view'),
    path('ical/<uuid:token>/', schedule_views.ical_feed, name='ical_feed'),
    path('tipoactividad/', schedule_views.TipoActividadListView.as_view(), name='tipoactividad_list'),
    path('tipoactividad/create/', schedule_views.TipoActividadCreateView.as_view(), name='tipoactividad_create'),
    path('tipoactividad/<int:pk>/update/', schedule_views.TipoActividadUpdateView.as_view(), name='tipoactividad_update'),
    path('tipoactividad/<int:pk>/delete/', schedule_views.TipoActividadDeleteView.as_view(), name='tipoactividad_delete'),
    # AJAX endpoints for activity types
    path('ajax/tipoactividad/create/', schedule_views.ajax_create_tipo_actividad, name='ajax_create_tipo_actividad'),
    path('ajax/tipoactividad/<int:pk>/update/', schedule_views.ajax_update_tipo_actividad, name='ajax_update_tipo_actividad'),
    path('ajax/tipoactividad/<int:pk>/delete/', schedule_views.ajax_delete_tipo_actividad, name='ajax_delete_tipo_actividad'),
    path('ajax/tipoactividad/<int:pk>/activity_count/', schedule_views.ajax_get_activity_count, name='ajax_get_activity_count'),
    path('all_activities/', schedule_views.all_activities, name='all_activities'),
    path('activity/delete_misassigned/<int:pk>/', schedule_views.delete_misassigned_activity, name='delete_misassigned_activity'),
    path('activity/toggle_approval_from_dashboard/<int:pk>/', schedule_views.toggle_activity_approval_from_dashboard, name='toggle_activity_approval_from_dashboard'),
    # Activity versioning URLs
    path('activity/<int:pk>/versions/', schedule_views.activity_version_history, name='activity_version_history'),
    path('activity/<int:pk>/versions/<int:version_id>/', schedule_views.activity_version_detail, name='activity_version_detail'),
    path('activity/<int:pk>/versions/<int:version_id>/restore/', schedule_views.activity_restore_version, name='activity_restore_version'),
    # PDF Reports
    path('reports/agenda/<int:titulacion_id>/', schedule_views.generate_agenda_report, name='generate_agenda_report_titulacion'),
    path('reports/agenda/', schedule_views.generate_agenda_report, name='generate_agenda_report_all'),
    # iCal Management
    path('ical/create_automatic/', schedule_views.create_automatic_icals, name='create_automatic_icals'),
    path('ical/management/', schedule_views.ical_management, name='ical_management'),
    path('', agenda_views.home, name='home'),
    path('agenda_settings/', agenda_views.agenda_settings, name='agenda_settings'),
    path('ajax/agenda_settings/update/', agenda_views.ajax_update_agenda_settings, name='ajax_update_agenda_settings'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
