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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('ajax/get_cursos/', schedule_views.get_cursos, name='get_cursos'),
    path('ajax/get_semestres/', schedule_views.get_semestres, name='get_semestres'),
    path('ajax/get_asignaturas/', schedule_views.get_asignaturas, name='get_asignaturas'),
    path('activity/new/', schedule_views.activity_form, name='activity_new'),
    path('activity/edit/<int:pk>/', schedule_views.activity_form, name='activity_edit'),
    path('activity/delete/<int:pk>/', schedule_views.activity_delete, name='activity_delete'),
    path('activity/list/', schedule_views.activity_list, name='activity_list'),
    path('calendar_views/', schedule_views.calendar_view_panel, name='calendar_view_panel'),
    path('calendar_views/new/', schedule_views.create_calendar_view, name='create_calendar_view'),
    path('calendar_views/delete/<int:pk>/', schedule_views.delete_calendar_view, name='delete_calendar_view'),
    path('ical/<uuid:token>/', schedule_views.ical_feed, name='ical_feed'),
    path('activity/delete_misassigned/<int:pk>/', schedule_views.delete_misassigned_activity, name='delete_misassigned_activity'),
    path('', agenda_views.home, name='home'),
]
