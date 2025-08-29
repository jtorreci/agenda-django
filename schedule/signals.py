from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Actividad, ActividadVersion
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(pre_save, sender=Actividad)
def create_activity_version_on_update(sender, instance, **kwargs):
    """
    Create a version snapshot before updating an existing activity.
    This signal fires before saving an Actividad instance.
    """
    # Only create version for existing activities (updates, not creates)
    if instance.pk:
        try:
            # Get the current version from database before it's updated
            old_instance = Actividad.objects.get(pk=instance.pk)
            
            # Get the next version number for this activity
            last_version = ActividadVersion.objects.filter(
                actividad_original=old_instance
            ).order_by('-version_numero').first()
            
            next_version_number = (last_version.version_numero + 1) if last_version else 1
            
            # Create snapshot of current state
            asignaturas_data = []
            for asignatura in old_instance.asignaturas.all():
                asignaturas_data.append({
                    'id': asignatura.id,
                    'nombre': asignatura.nombre
                })
            
            tipo_actividad_data = {
                'id': old_instance.tipo_actividad.id,
                'nombre': old_instance.tipo_actividad.nombre
            } if old_instance.tipo_actividad else {}
            
            # Get the user who is making the modification
            modified_by = getattr(instance, '_modified_by', None)
            if not modified_by:
                # If no user is set, skip versioning (this shouldn't happen in normal operation)
                return

            # Create version entry
            ActividadVersion.objects.create(
                actividad_original=old_instance,
                version_numero=next_version_number,
                modificada_por=modified_by,
                comentario_version=getattr(instance, '_version_comment', ''),  # Optional comment
                
                # Copy all current field values
                nombre=old_instance.nombre,
                descripcion=old_instance.descripcion,
                fecha_inicio=old_instance.fecha_inicio,
                fecha_fin=old_instance.fecha_fin,
                evaluable=old_instance.evaluable,
                porcentaje_evaluacion=old_instance.porcentaje_evaluacion,
                no_recuperable=old_instance.no_recuperable,
                aprobada=old_instance.aprobada,
                activa=old_instance.activa,
                
                # Store related data as JSON snapshots
                asignaturas_snapshot=asignaturas_data,
                tipo_actividad_snapshot=tipo_actividad_data
            )
            
        except Actividad.DoesNotExist:
            # This shouldn't happen, but just in case
            pass
        except Exception as e:
            # Log the error but don't break the save operation
            print(f"Error creating activity version: {e}")