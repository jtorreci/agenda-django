from django.db import models
from django.db.models import Q
from academics.models import AcademicYear, Asignatura
from users.models import CustomUser
import uuid

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'tipo de actividad'
        verbose_name_plural = 'tipos de actividad'

    def __str__(self):
        return self.nombre

class ActividadGrupo(models.Model):
    """
    Representa un grupo específico de una actividad.
    Cada actividad puede tener uno o más grupos con horarios y descripciones diferentes.
    """
    actividad = models.ForeignKey('Actividad', on_delete=models.CASCADE, related_name='grupos')
    nombre_grupo = models.CharField(max_length=100, help_text="Nombre del grupo (ej: 'A', 'B', 'Mañana', '1')")
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción del grupo (instrucciones específicas, etc.)")
    lugar = models.CharField(max_length=255, blank=True, null=True, help_text="Lugar donde se realiza el grupo (aula, laboratorio, etc.)")
    orden = models.PositiveIntegerField(default=1, help_text="Orden de visualización de los grupos")
    
    class Meta:
        ordering = ['orden', 'fecha_inicio']
        unique_together = ['actividad', 'nombre_grupo']
        verbose_name = "grupo de actividad"
        verbose_name_plural = "grupos de actividades"
    
    def __str__(self):
        return f"{self.actividad.nombre} - Grupo {self.nombre_grupo}"

class ActividadQuerySet(models.QuerySet):
    """QuerySet personalizado para filtrar por estados"""

    def visible(self):
        """Actividades visibles (no borradas ni archivadas)"""
        return self.filter(estado='visible')

    def borradas(self):
        """Actividades borradas por profesores (coordinador puede restaurar)"""
        return self.filter(estado='borrada')

    def archivadas(self):
        """Actividades archivadas por coordinadores (solo admin puede ver)"""
        return self.filter(estado='archivada')

    def activas_legacy(self):
        """Compatibilidad con campo legacy activa"""
        return self.exclude(estado='archivada').filter(activa=True)

    def in_active_year(self):
        """Activities of the active academic year (empty when no year is active)."""
        return self.filter(academic_year__state=AcademicYear.STATE_ACTIVE)

class ActividadManager(models.Manager):
    """Manager personalizado con métodos de filtrado por estado"""

    def get_queryset(self):
        return ActividadQuerySet(self.model, using=self._db)

    def visible(self):
        return self.get_queryset().visible()

    def borradas(self):
        return self.get_queryset().borradas()

    def archivadas(self):
        return self.get_queryset().archivadas()

    def in_active_year(self):
        return self.get_queryset().in_active_year()

class Actividad(models.Model):
    # Estados de actividad
    ESTADO_VISIBLE = 'visible'
    ESTADO_BORRADA = 'borrada'
    ESTADO_ARCHIVADA = 'archivada'

    ESTADO_CHOICES = [
        (ESTADO_VISIBLE, 'Visible'),
        (ESTADO_BORRADA, 'Borrada'),
        (ESTADO_ARCHIVADA, 'Archivada'),
    ]

    nombre = models.CharField(max_length=255)
    asignaturas = models.ManyToManyField(Asignatura)
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE, verbose_name='tipo de actividad')
    # Every activity belongs to exactly one academic year. Only activities of the
    # active year are editable; new activities always get the active year.
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='activities', verbose_name='curso académico'
    )
    # Source activity when this one was imported from a previous academic year.
    copied_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='copies', verbose_name='copiada de'
    )

    # Campo estado principal
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_VISIBLE,
        help_text="Estado actual de la actividad"
    )

    # Campos que se migrarán a ActividadGrupo - mantener temporalmente
    fecha_inicio = models.DateTimeField('fecha de inicio')
    fecha_fin = models.DateTimeField('fecha de fin')
    descripcion = models.TextField('descripción', blank=True, null=True)
    evaluable = models.BooleanField(default=False)
    porcentaje_evaluacion = models.DecimalField('porcentaje de evaluación', max_digits=5, decimal_places=2, default=0.0)
    no_recuperable = models.BooleanField(default=False)
    aprobada = models.BooleanField(default=False)  # Mantiene lógica de workflow independiente

    # Campos legacy - mantener por compatibilidad
    activa = models.BooleanField(default=True, help_text="LEGACY: Usar campo 'estado' en su lugar")
    grupo_id = models.UUIDField(blank=True, null=True, help_text="Identificador para agrupar actividades de múltiples grupos - DEPRECATED")

    # Manager personalizado
    objects = ActividadManager()

    class Meta:
        verbose_name = 'actividad'
        verbose_name_plural = 'actividades'
        constraints = [
            models.UniqueConstraint(
                fields=['copied_from', 'academic_year'],
                # Only non-deleted copies are unique: a deleted copy frees the
                # source for a new import (see schedule.year_import.live_copies).
                condition=Q(copied_from__isnull=False, estado='visible'),
                name='schedule_unique_activity_import_per_year',
            )
        ]

    @property
    def is_read_only(self):
        """Activities outside the active academic year cannot be modified."""
        return self.academic_year.state != AcademicYear.STATE_ACTIVE
    
    @property
    def grupos_count(self):
        """Número de grupos asociados a esta actividad"""
        return self.grupos.count()
    
    @property
    def primer_grupo(self):
        """Primer grupo de la actividad (para compatibilidad)"""
        return self.grupos.first()

    def save(self, *args, **kwargs):
        # New activities always belong to the active academic year.
        if self.academic_year_id is None:
            self.academic_year = AcademicYear.require_active()

        # Apply automatic approval logic only when creating a new activity or when approval status hasn't been manually set
        if not self.pk or not hasattr(self, '_approval_manually_set'):
            self.aprobada = self._get_default_approval_status()

        # Sincronizar campo legacy 'activa' con nuevo campo 'estado'
        self.activa = (self.estado == self.ESTADO_VISIBLE)

        super().save(*args, **kwargs)

    def _get_default_approval_status(self):
        """
        Determine default approval status based on evaluation criteria:
        - Non-evaluable activities: approved by default
        - Evaluable with <10% weight: approved by default  
        - Evaluable with >=10% weight: not approved by default (requires coordinator approval)
        """
        if not self.evaluable:
            return True  # Non-evaluable activities are approved by default
        elif self.porcentaje_evaluacion < 10.0:
            return True  # Evaluable with <10% weight are approved by default
        else:
            return False  # Evaluable with >=10% weight require manual approval

    def set_approval_manually(self, approved_status, modified_by=None):
        """
        Manually set approval status (used by coordinators)
        This prevents automatic approval logic from overriding manual decisions
        """
        self._approval_manually_set = True
        self.aprobada = approved_status
        if modified_by:
            self._modified_by = modified_by
            self._version_comment = f'Estado de aprobación cambiado a {"aprobada" if approved_status else "no aprobada"}'
        self.save()

    # Métodos para gestión de estados
    def es_visible(self):
        """Retorna True si la actividad es visible"""
        return self.estado == self.ESTADO_VISIBLE

    def es_borrada(self):
        """Retorna True si la actividad está borrada"""
        return self.estado == self.ESTADO_BORRADA

    def es_archivada(self):
        """Retorna True si la actividad está archivada"""
        return self.estado == self.ESTADO_ARCHIVADA

    def borrar(self, usuario=None):
        """Borra la actividad (profesor) - coordinador puede restaurar"""
        self.estado = self.ESTADO_BORRADA
        self.save()
        # Crear log si se proporciona usuario
        if usuario:
            from schedule.models import LogActividad
            LogActividad.objects.create(
                object_type='actividad',
                object_name=self.nombre,
                object_id=self.id,
                actividad=self,
                usuario=usuario,
                tipo_log='Deletion',
                details=f'Actividad borrada (estado: {self.estado})'
            )

    def restaurar(self, usuario=None):
        """Restaura la actividad desde borrada a visible"""
        if self.es_borrada():
            self.estado = self.ESTADO_VISIBLE
            self.save()
            # Crear log si se proporciona usuario
            if usuario:
                from schedule.models import LogActividad
                LogActividad.objects.create(
                    object_type='actividad',
                    object_name=self.nombre,
                    object_id=self.id,
                    actividad=self,
                    usuario=usuario,
                    tipo_log='Restoration',
                    details=f'Actividad restaurada (estado: {self.estado})'
                )

    def archivar(self, usuario=None):
        """Archiva la actividad (coordinador) - solo admin puede restaurar"""
        self.estado = self.ESTADO_ARCHIVADA
        self.save()
        # Crear log si se proporciona usuario
        if usuario:
            from schedule.models import LogActividad
            LogActividad.objects.create(
                object_type='actividad',
                object_name=self.nombre,
                object_id=self.id,
                actividad=self,
                usuario=usuario,
                tipo_log='Archive',
                details=f'Actividad archivada (estado: {self.estado})'
            )

    def restaurar_desde_archivo(self, usuario=None):
        """Restaura la actividad desde archivada a borrada (solo admin)"""
        if self.es_archivada():
            self.estado = self.ESTADO_BORRADA
            self.save()
            # Crear log si se proporciona usuario
            if usuario:
                from schedule.models import LogActividad
                LogActividad.objects.create(
                    object_type='actividad',
                    object_name=self.nombre,
                    object_id=self.id,
                    actividad=self,
                    usuario=usuario,
                    tipo_log='Restoration',
                    details=f'Actividad restaurada desde archivo (estado: {self.estado})'
                )

    def get_estado_display_custom(self):
        """Retorna el estado en formato display personalizado"""
        return dict(self.ESTADO_CHOICES).get(self.estado, self.estado)

    def __str__(self):
        return self.nombre

class LogActividad(models.Model):
    OBJECT_TYPE_CHOICES = [
        ('actividad', 'Actividad'),
        ('tipo_actividad', 'Tipo de actividad'),
        ('coordinador', 'Asignación de coordinador'),
    ]

    # tipo_log stores historical values (some in English, some in Spanish).
    # Stored values must not change; these maps only drive the Spanish display.
    TIPO_LOG_LABELS = {
        'Creation': 'Creación',
        'Modification': 'Modificación',
        'Deletion': 'Eliminación',
        'Reactivation': 'Reactivación',
        'Restoration': 'Restauración',
        'Archive': 'Archivado',
        'Version Restore': 'Restauración de versión',
        'Report Generation': 'Generación de informe',
        'iCal Generation': 'Generación de iCal',
        'iCal Deletion': 'Eliminación de iCal',
        'Aprobación desde Dashboard': 'Aprobación desde el panel',
        'Desaprobación desde Dashboard': 'Desaprobación desde el panel',
    }
    TIPO_LOG_BADGES = {
        'Creación': 'success',
        'Asignación': 'success',
        'Modificación': 'info',
        'Eliminación': 'danger',
    }
    
    id_log = models.AutoField(primary_key=True)
    # Keep actividad field for backward compatibility, but make it optional
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, null=True, blank=True)
    # New fields for generic logging
    object_type = models.CharField('tipo de objeto', max_length=20, choices=OBJECT_TYPE_CHOICES, default='actividad')
    object_name = models.CharField('nombre del objeto', max_length=255)  # Name of the object being logged
    object_id = models.PositiveIntegerField('id del objeto', null=True, blank=True)  # ID of the object being logged
    
    timestamp = models.DateTimeField('fecha y hora', auto_now_add=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    tipo_log = models.CharField('tipo de registro', max_length=50)
    details = models.TextField('detalles', blank=True, null=True)  # Additional details about the action

    class Meta:
        verbose_name = 'registro de actividad'
        verbose_name_plural = 'registros de actividad'
        ordering = ['-timestamp']

    @property
    def tipo_log_label(self):
        """Spanish label for the stored log type."""
        return self.TIPO_LOG_LABELS.get(self.tipo_log, self.tipo_log)

    @property
    def tipo_log_badge(self):
        """Bootstrap badge colour for the log type."""
        return self.TIPO_LOG_BADGES.get(self.tipo_log_label, 'secondary')

    def __str__(self):
        return f"Log {self.tipo_log} for {self.object_type}: {self.object_name} by {self.usuario.username} at {self.timestamp}"

class VistaCalendario(models.Model):
    nombre = models.CharField(max_length=255)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    asignaturas = models.ManyToManyField(Asignatura)
    tipos_actividad = models.ManyToManyField(TipoActividad, verbose_name='tipos de actividad')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        verbose_name = 'calendario'
        verbose_name_plural = 'calendarios'

    def __str__(self):
        return self.nombre

class ActividadVersion(models.Model):
    """
    Stores historical versions of activities for version control and rollback functionality.
    Each time an activity is modified, the current version is saved here before applying changes.
    """
    # Version control metadata
    actividad_original = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name='versiones')
    version_numero = models.PositiveIntegerField()  # Auto-incremented version number
    modificada_por = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    fecha_modificacion = models.DateTimeField(auto_now_add=True)
    comentario_version = models.TextField(blank=True, null=True)  # Optional comment about the change
    
    # Snapshot of all activity fields at the time of modification
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    evaluable = models.BooleanField(default=False)
    porcentaje_evaluacion = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    no_recuperable = models.BooleanField(default=False)
    aprobada = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)
    
    # Store related data as JSON or text fields since we can't use ManyToMany in versions
    asignaturas_snapshot = models.JSONField(default=list)  # Store list of asignatura IDs and names
    tipo_actividad_snapshot = models.JSONField(default=dict)  # Store tipo_actividad ID and name

    class Meta:
        verbose_name = 'versión de actividad'
        verbose_name_plural = 'versiones de actividad'
        ordering = ['-fecha_modificacion']
        unique_together = ['actividad_original', 'version_numero']

    def __str__(self):
        return f"{self.actividad_original.nombre} - v{self.version_numero} ({self.fecha_modificacion.strftime('%Y-%m-%d %H:%M')})"

    def get_asignaturas_names(self):
        """Return comma-separated list of asignatura names from snapshot"""
        if self.asignaturas_snapshot:
            return ', '.join([asig['nombre'] for asig in self.asignaturas_snapshot])
        return 'N/D'