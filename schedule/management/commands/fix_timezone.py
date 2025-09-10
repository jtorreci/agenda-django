from django.core.management.base import BaseCommand
from django.utils import timezone
from schedule.models import Actividad
import pytz
from datetime import timedelta

class Command(BaseCommand):
    help = 'Corrige las fechas de actividades que se guardaron con zona horaria incorrecta'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular la corrección sin aplicar cambios',
        )
        parser.add_argument(
            '--offset-hours',
            type=int,
            default=1,
            help='Horas a ajustar (default: 1 hora)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        offset_hours = options['offset_hours']
        
        madrid_tz = pytz.timezone('Europe/Madrid')
        
        self.stdout.write(f"{'SIMULANDO' if dry_run else 'APLICANDO'} corrección de zona horaria...")
        self.stdout.write(f"Ajuste: {offset_hours} horas")
        
        # Corregir actividades
        actividades = Actividad.objects.all()
        actividades_count = 0
        
        for actividad in actividades:
            old_inicio = actividad.fecha_inicio
            old_fin = actividad.fecha_fin
            
            # Ajustar fechas
            nueva_inicio = old_inicio + timedelta(hours=offset_hours)
            nueva_fin = old_fin + timedelta(hours=offset_hours)
            
            self.stdout.write(f"Actividad '{actividad.nombre}':")
            self.stdout.write(f"  Inicio: {old_inicio} -> {nueva_inicio}")
            self.stdout.write(f"  Fin: {old_fin} -> {nueva_fin}")
            
            if not dry_run:
                actividad.fecha_inicio = nueva_inicio
                actividad.fecha_fin = nueva_fin
                actividad.save()
            
            actividades_count += 1
        
        # Corregir versiones de actividades si el modelo existe
        versiones_count = 0
        try:
            from schedule.models import ActividadVersion
            versiones = ActividadVersion.objects.all()
            
            for version in versiones:
                old_inicio = version.fecha_inicio
                old_fin = version.fecha_fin
                
                nueva_inicio = old_inicio + timedelta(hours=offset_hours)
                nueva_fin = old_fin + timedelta(hours=offset_hours)
                
                if not dry_run:
                    version.fecha_inicio = nueva_inicio
                    version.fecha_fin = nueva_fin
                    version.save()
                
                versiones_count += 1
        except ImportError:
            # ActividadVersion no existe en esta versión
            self.stdout.write("Modelo ActividadVersion no encontrado, omitiendo...")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Simuladas' if dry_run else 'Corregidas'} {actividades_count} actividades "
                f"y {versiones_count} versiones de actividades"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Ejecuta sin --dry-run para aplicar los cambios"
                )
            )