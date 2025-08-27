from django.db import models
from academics.models import Asignatura
from users.models import CustomUser
import uuid

class TipoActividad(models.Model):
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre

class Actividad(models.Model):
    nombre = models.CharField(max_length=255)
    asignaturas = models.ManyToManyField(Asignatura)
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    descripcion = models.TextField(blank=True, null=True)
    evaluable = models.BooleanField(default=False)
    porcentaje_evaluacion = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    no_recuperable = models.BooleanField(default=False)
    aprobada = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class LogActividad(models.Model):
    id_log = models.AutoField(primary_key=True)
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    tipo_log = models.CharField(max_length=50)

    def __str__(self):
        return f"Log {self.tipo_log} for {self.actividad.nombre} by {self.usuario.username} at {self.timestamp}"

class VistaCalendario(models.Model):
    nombre = models.CharField(max_length=255)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    asignaturas = models.ManyToManyField(Asignatura)
    tipos_actividad = models.ManyToManyField(TipoActividad)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.nombre