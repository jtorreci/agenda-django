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
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    tipo_actividad = models.ForeignKey(TipoActividad, on_delete=models.CASCADE)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class VistaCalendario(models.Model):
    nombre = models.CharField(max_length=255)
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    asignaturas = models.ManyToManyField(Asignatura)
    tipos_actividad = models.ManyToManyField(TipoActividad)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.nombre