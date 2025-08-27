from django.core.management.base import BaseCommand
from schedule.models import TipoActividad

class Command(BaseCommand):
    help = 'Creates initial activity types for the application.'

    def handle(self, *args, **options):
        activity_types = [
            "Práctica de Laboratorio",
            "Examen Parcial",
            "Entrega Trabajo",
            "Exposición Oral en Clase",
        ]

        for activity_type_name in activity_types:
            obj, created = TipoActividad.objects.get_or_create(nombre=activity_type_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created activity type: "{activity_type_name}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Activity type "{activity_type_name}" already exists.'))
