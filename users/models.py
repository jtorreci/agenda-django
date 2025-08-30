from django.contrib.auth.models import AbstractUser
from django.db import models
from academics.models import Asignatura, Titulacion


class TipoPerfil(models.Model):
    """Tipos de perfil configurables desde el dashboard"""
    nombre = models.CharField(max_length=50, unique=True)
    codigo = models.CharField(max_length=20, unique=True, help_text="Código único para usar en el código (ej: STUDENT, TEACHER)")
    descripcion = models.TextField(blank=True, help_text="Descripción del perfil y sus permisos")
    color = models.CharField(max_length=7, default='#6c757d', help_text="Color para badges en formato hex (#ffffff)")
    icono = models.CharField(max_length=50, default='bi-person', help_text="Icono Bootstrap Icons (ej: bi-person, bi-gear)")
    
    # Permisos como JSON field (para futuro uso)
    permisos = models.JSONField(default=dict, blank=True, help_text="Configuración de permisos en formato JSON")
    
    # Control del sistema
    es_sistema = models.BooleanField(default=False, help_text="Los perfiles del sistema no se pueden eliminar")
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición en interfaces")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'Tipo de Perfil'
        verbose_name_plural = 'Tipos de Perfil'
    
    def __str__(self):
        return self.nombre
    
    def usuarios_con_perfil(self):
        """Retorna cantidad de usuarios con este perfil"""
        return self.asignaciones.filter(activa=True).count()


class AsignacionPerfil(models.Model):
    """Tabla intermedia para asignaciones de perfiles con metadata"""
    usuario = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='asignaciones_perfil')
    tipo_perfil = models.ForeignKey(TipoPerfil, on_delete=models.CASCADE, related_name='asignaciones')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    asignado_por = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, 
                                   related_name='asignaciones_realizadas', null=True, blank=True)
    activa = models.BooleanField(default=True)
    notas = models.TextField(blank=True, help_text="Notas opcionales sobre esta asignación")
    fecha_desactivacion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('usuario', 'tipo_perfil')
        ordering = ['-fecha_asignacion']
        verbose_name = 'Asignación de Perfil'
        verbose_name_plural = 'Asignaciones de Perfil'
    
    def __str__(self):
        return f'{self.usuario.username} - {self.tipo_perfil.nombre}'


class CustomUser(AbstractUser):
    ROLE_STUDENT = 'STUDENT'
    ROLE_TEACHER = 'TEACHER'
    ROLE_COORDINATOR = 'COORDINATOR'
    ROLE_ADMIN = 'ADMIN'

    ROLE_CHOICES = (
        (ROLE_STUDENT, 'Student'),
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_COORDINATOR, 'Coordinator'),
        (ROLE_ADMIN, 'Admin'),
    )
    # SISTEMA LEGACY - Mantener por compatibilidad
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    subjects = models.ManyToManyField(Asignatura, blank=True)
    coordinated_titulaciones = models.ManyToManyField(Titulacion, blank=True)
    
    # NUEVO SISTEMA - Perfiles dinámicos
    tipos_perfil = models.ManyToManyField(TipoPerfil, through=AsignacionPerfil, 
                                         through_fields=('usuario', 'tipo_perfil'), blank=True)
    
    def tiene_perfil(self, codigo_perfil):
        """Verifica si el usuario tiene un perfil específico (nuevo sistema)"""
        return self.tipos_perfil.filter(codigo=codigo_perfil, activo=True).exists()
    
    def perfiles_activos(self):
        """Retorna todos los perfiles activos del usuario"""
        return self.tipos_perfil.filter(activo=True, asignaciones__activa=True)
    
    def asignar_perfil(self, codigo_perfil, asignado_por=None, notas=""):
        """Asigna un perfil al usuario"""
        try:
            tipo_perfil = TipoPerfil.objects.get(codigo=codigo_perfil, activo=True)
            asignacion, created = AsignacionPerfil.objects.get_or_create(
                usuario=self,
                tipo_perfil=tipo_perfil,
                defaults={
                    'asignado_por': asignado_por,
                    'notas': notas,
                    'activa': True
                }
            )
            if not created and not asignacion.activa:
                asignacion.activa = True
                asignacion.fecha_desactivacion = None
                asignacion.save()
            return asignacion
        except TipoPerfil.DoesNotExist:
            return None
    
    def remover_perfil(self, codigo_perfil):
        """Remueve un perfil del usuario"""
        try:
            from django.utils import timezone
            asignacion = AsignacionPerfil.objects.get(
                usuario=self,
                tipo_perfil__codigo=codigo_perfil,
                activa=True
            )
            asignacion.activa = False
            asignacion.fecha_desactivacion = timezone.now()
            asignacion.save()
            return True
        except AsignacionPerfil.DoesNotExist:
            return False
    
    # MÉTODOS DE COMPATIBILIDAD - Funcionan con ambos sistemas
    def es_estudiante(self):
        """Compatible con sistema legacy y nuevo"""
        return (self.tiene_perfil('STUDENT') or self.role == 'STUDENT')
    
    def es_profesor(self):
        """Compatible con sistema legacy y nuevo"""
        return (self.tiene_perfil('TEACHER') or 
                self.tiene_perfil('COORDINATOR') or 
                self.tiene_perfil('ADMIN') or
                self.role in ['TEACHER', 'COORDINATOR', 'ADMIN'])
    
    def es_coordinador(self):
        """Compatible con sistema legacy y nuevo"""
        return (self.tiene_perfil('COORDINATOR') or 
                self.tiene_perfil('ADMIN') or
                self.role in ['COORDINATOR', 'ADMIN'])
    
    def es_admin(self):
        """Compatible con sistema legacy y nuevo"""
        return (self.tiene_perfil('ADMIN') or 
                self.role == 'ADMIN' or 
                self.is_superuser)
    
    def es_equipo_direccion(self):
        """Nuevo método para equipo de dirección"""
        return self.tiene_perfil('DIRECTION_TEAM')
    
    def get_perfiles_display(self):
        """Retorna una lista legible de los perfiles del usuario"""
        perfiles = list(self.perfiles_activos().values_list('nombre', flat=True))
        if not perfiles and self.role:
            # Fallback al sistema legacy
            perfiles = [self.get_role_display()]
        return perfiles
    
    def get_perfiles_badges(self):
        """Retorna información para mostrar badges de perfiles en templates"""
        return self.perfiles_activos().values('nombre', 'color', 'icono')

class LoginAttempt(models.Model):
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()

    def __str__(self):
        return f'{self.username} - {self.timestamp} - {"Success" if self.success else "Failed"}'
