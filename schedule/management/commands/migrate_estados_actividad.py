from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from schedule.models import Actividad
from django.utils import timezone

class Command(BaseCommand):
    help = 'Migra el campo legacy "activa" al nuevo campo "estado" en las actividades'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular la migración sin aplicar cambios',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset: cambiar todas las actividades a visible (para testing)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reset = options['reset']

        if reset:
            return self.reset_all_to_visible(dry_run)

        self.stdout.write(f"{'SIMULANDO' if dry_run else 'APLICANDO'} migración de estados...")

        # Contar actividades a migrar
        total_actividades = Actividad.objects.all().count()
        actividades_activas = Actividad.objects.filter(activa=True).count()
        actividades_inactivas = Actividad.objects.filter(activa=False).count()

        self.stdout.write(f"Actividades encontradas:")
        self.stdout.write(f"  - Total: {total_actividades}")
        self.stdout.write(f"  - Activas (activa=True): {actividades_activas}")
        self.stdout.write(f"  - Inactivas (activa=False): {actividades_inactivas}")
        self.stdout.write("")

        migrated_to_visible = 0
        migrated_to_borrada = 0

        with transaction.atomic():
            # Crear savepoint para rollback en dry-run
            if dry_run:
                sid = transaction.savepoint()

            try:
                # Migrar actividades activas -> visible
                actividades_activas_list = Actividad.objects.filter(activa=True)
                for actividad in actividades_activas_list:
                    if actividad.estado != 'visible':  # Solo cambiar si no está ya migrada
                        actividad.estado = Actividad.ESTADO_VISIBLE
                        if not dry_run:
                            actividad.save()
                        migrated_to_visible += 1
                        if migrated_to_visible <= 5:  # Mostrar solo los primeros 5
                            self.stdout.write(f"  + '{actividad.nombre}' -> visible")

                # Migrar actividades inactivas -> borrada
                actividades_inactivas_list = Actividad.objects.filter(activa=False)
                for actividad in actividades_inactivas_list:
                    if actividad.estado != 'borrada':  # Solo cambiar si no está ya migrada
                        actividad.estado = Actividad.ESTADO_BORRADA
                        if not dry_run:
                            actividad.save()
                        migrated_to_borrada += 1
                        if migrated_to_borrada <= 5:  # Mostrar solo las primeras 5
                            self.stdout.write(f"  + '{actividad.nombre}' -> borrada")

                if dry_run:
                    transaction.savepoint_rollback(sid)
                    self.stdout.write("")
                    self.stdout.write(
                        self.style.WARNING("DRY RUN completado - cambios no aplicados")
                    )
                else:
                    self.stdout.write("")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Migración completada exitosamente:"
                        )
                    )

                self.stdout.write(f"  - Migradas a VISIBLE: {migrated_to_visible}")
                self.stdout.write(f"  - Migradas a BORRADA: {migrated_to_borrada}")
                self.stdout.write("")

                # Mostrar estadísticas post-migración
                if not dry_run:
                    self.show_post_migration_stats()
                else:
                    self.stdout.write("Para ver estadísticas finales, ejecuta sin --dry-run")

            except Exception as e:
                if dry_run:
                    transaction.savepoint_rollback(sid)
                self.stdout.write(
                    self.style.ERROR(f"Error durante la migración: {str(e)}")
                )
                raise

    def reset_all_to_visible(self, dry_run):
        """Reset todas las actividades a visible (para testing)"""
        self.stdout.write(f"{'SIMULANDO' if dry_run else 'APLICANDO'} reset a visible...")

        total_actividades = Actividad.objects.all().count()
        reset_count = 0

        with transaction.atomic():
            if dry_run:
                sid = transaction.savepoint()

            try:
                for actividad in Actividad.objects.all():
                    if actividad.estado != 'visible':
                        actividad.estado = Actividad.ESTADO_VISIBLE
                        if not dry_run:
                            actividad.save()
                        reset_count += 1
                        if reset_count <= 10:
                            self.stdout.write(f"  + '{actividad.nombre}' -> visible")

                if dry_run:
                    transaction.savepoint_rollback(sid)
                    self.stdout.write(self.style.WARNING("DRY RUN completado"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Reset completado: {reset_count} actividades -> visible"))

            except Exception as e:
                if dry_run:
                    transaction.savepoint_rollback(sid)
                self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
                raise

    def show_post_migration_stats(self):
        """Muestra estadísticas después de la migración"""
        visible_count = Actividad.objects.filter(estado='visible').count()
        borrada_count = Actividad.objects.filter(estado='borrada').count()
        archivada_count = Actividad.objects.filter(estado='archivada').count()

        self.stdout.write("Estadísticas post-migración:")
        self.stdout.write(f"  - Estados VISIBLE: {visible_count}")
        self.stdout.write(f"  - Estados BORRADA: {borrada_count}")
        self.stdout.write(f"  - Estados ARCHIVADA: {archivada_count}")
        self.stdout.write("")

        # Verificar consistencia
        inconsistent = Actividad.objects.exclude(
            models.Q(activa=True, estado='visible') |
            models.Q(activa=False, estado='borrada') |
            models.Q(activa=False, estado='archivada')
        ).count()

        if inconsistent > 0:
            self.stdout.write(self.style.WARNING(f"WARNING: {inconsistent} actividades con inconsistencias entre 'activa' y 'estado'"))
        else:
            self.stdout.write(self.style.SUCCESS("OK: Todos los campos estan consistentes"))