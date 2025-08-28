from django.core.management.base import BaseCommand
from schedule.models import Actividad

class Command(BaseCommand):
    help = 'Apply automatic approval logic to existing activities'

    def handle(self, *args, **options):
        activities = Actividad.objects.all()
        updated_count = 0
        
        for activity in activities:
            old_approval_status = activity.aprobada
            new_approval_status = activity._get_default_approval_status()
            
            if old_approval_status != new_approval_status:
                activity.aprobada = new_approval_status
                activity.save()
                updated_count += 1
                
                self.stdout.write(
                    f"Updated activity '{activity.nombre}': "
                    f"evaluable={activity.evaluable}, "
                    f"percentage={activity.porcentaje_evaluacion}%, "
                    f"approved: {old_approval_status} -> {new_approval_status}"
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated_count} activities with automatic approval logic'
            )
        )