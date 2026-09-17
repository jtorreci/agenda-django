from django.urls import path

from . import views

urlpatterns = [
    path('', views.ical_import_list, name='ical_import_list'),
    path('<int:pk>/', views.ical_import_detail, name='ical_import_detail'),
    path('<int:pk>/apply/', views.ical_import_apply, name='ical_import_apply'),
    path('<int:pk>/delete/', views.ical_import_delete, name='ical_import_delete'),
]
