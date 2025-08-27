import os
import django
import csv

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
django.setup()

from academics.models import Titulacion, Asignatura

def import_data():
    # Import titulaciones
    with open('titulaciones.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            Titulacion.objects.get_or_create(nombre=row[0])

    # Import asignaturas
    with open('asignaturas.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)  # Skip header
        for row in reader:
            titulacion_nombre = row[3]
            titulacion = Titulacion.objects.get(nombre=titulacion_nombre)
            Asignatura.objects.get_or_create(
                nombre=row[0],
                curso=row[1],
                semestre=row[2],
                titulacion=titulacion
            )

if __name__ == '__main__':
    import_data()
