import os
import csv
from django.core.management.base import BaseCommand
from academics.models import Titulacion, Asignatura

class Command(BaseCommand):
    help = 'Imports initial data from CSV files'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting data import...'))

        # Import titulaciones
        with open('titulaciones.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                Titulacion.objects.get_or_create(nombre=row[0])
        self.stdout.write(self.style.SUCCESS('Titulaciones imported successfully.'))

        # Import asignaturas
        with open('asignaturas.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader)  # Skip header
            for row in reader:
                titulacion_nombre = row[3]
                try:
                    titulacion, created = Titulacion.objects.get_or_create(nombre=titulacion_nombre)
                    Asignatura.objects.get_or_create(
                        nombre=row[0],
                        curso=row[1],
                        semestre=row[2],
                        titulacion=titulacion
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error importing asignatura {row[0]} for titulacion {titulacion_nombre}: {e}'))
        self.stdout.write(self.style.SUCCESS('Asignaturas imported successfully.'))

        self.stdout.write(self.style.SUCCESS('Data import completed.'))
