from django.db import models

class Titulacion(models.Model):
    nombre = models.CharField(max_length=255)
    coordinador = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='coordinated_titulaciones_as_coordinator')

    def __str__(self):
        return self.nombre

class Asignatura(models.Model):
    nombre = models.CharField(max_length=255)
    titulacion = models.ForeignKey(Titulacion, on_delete=models.CASCADE)
    curso = models.IntegerField()
    semestre = models.IntegerField()
    coordinator = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='coordinated_subjects') # New field

    def __str__(self):
        return self.nombre