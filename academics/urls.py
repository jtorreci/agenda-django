from django.urls import path

from . import views

urlpatterns = [
    path('', views.catalogue_import_list, name='catalogue_import_list'),
    path('<int:pk>/', views.catalogue_import_detail, name='catalogue_import_detail'),
    path('<int:pk>/apply/', views.catalogue_import_apply, name='catalogue_import_apply'),
    path('<int:pk>/delete/', views.catalogue_import_delete, name='catalogue_import_delete'),
    path('years/<int:pk>/activate/', views.academic_year_activate, name='academic_year_activate'),
]
