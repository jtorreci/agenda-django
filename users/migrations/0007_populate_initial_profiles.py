# Generated migration for populating initial profile types

from django.db import migrations


def create_initial_profiles(apps, schema_editor):
    """Crear los tipos de perfil iniciales"""
    TipoPerfil = apps.get_model('users', 'TipoPerfil')
    
    perfiles_iniciales = [
        {
            'nombre': 'Estudiante',
            'codigo': 'STUDENT',
            'descripcion': 'Estudiante de la institución. Puede ver actividades y generar calendarios personalizados.',
            'color': '#17a2b8',  # info blue
            'icono': 'bi-person',
            'es_sistema': True,
            'orden': 1
        },
        {
            'nombre': 'Profesor',
            'codigo': 'TEACHER',
            'descripcion': 'Profesor de la institución. Puede crear y gestionar actividades para sus asignaturas.',
            'color': '#28a745',  # success green
            'icono': 'bi-person-workspace',
            'es_sistema': True,
            'orden': 2
        },
        {
            'nombre': 'Coordinador',
            'codigo': 'COORDINATOR',
            'descripcion': 'Coordinador de titulación. Puede aprobar actividades y gestionar asignaturas de su titulación.',
            'color': '#ffc107',  # warning yellow
            'icono': 'bi-person-gear',
            'es_sistema': True,
            'orden': 3
        },
        {
            'nombre': 'Administrador',
            'codigo': 'ADMIN',
            'descripcion': 'Administrador del sistema. Acceso completo a todas las funcionalidades.',
            'color': '#dc3545',  # danger red
            'icono': 'bi-shield-check',
            'es_sistema': True,
            'orden': 4
        },
        {
            'nombre': 'Equipo de Dirección',
            'codigo': 'DIRECTION_TEAM',
            'descripcion': 'Miembro del equipo de dirección. Acceso a funciones directivas y reportes especiales.',
            'color': '#6f42c1',  # purple
            'icono': 'bi-star',
            'es_sistema': False,
            'orden': 5
        }
    ]
    
    for perfil_data in perfiles_iniciales:
        TipoPerfil.objects.get_or_create(
            codigo=perfil_data['codigo'],
            defaults=perfil_data
        )


def reverse_create_initial_profiles(apps, schema_editor):
    """Reverso de la migración - eliminar perfiles creados"""
    TipoPerfil = apps.get_model('users', 'TipoPerfil')
    codigos_iniciales = ['STUDENT', 'TEACHER', 'COORDINATOR', 'ADMIN', 'DIRECTION_TEAM']
    TipoPerfil.objects.filter(codigo__in=codigos_iniciales).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_add_dynamic_profiles'),
    ]

    operations = [
        migrations.RunPython(create_initial_profiles, reverse_create_initial_profiles),
    ]