from django.db import models

class Titulacion(models.Model):
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre

class Asignatura(models.Model):
    nombre = models.CharField(max_length=255)
    titulacion = models.ForeignKey(Titulacion, on_delete=models.CASCADE)
    curso = models.IntegerField()
    semestre = models.IntegerField()

    def __str__(self):
        return self.nombre