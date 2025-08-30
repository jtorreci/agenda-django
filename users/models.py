from django.contrib.auth.models import AbstractUser
from django.db import models
from academics.models import Asignatura, Titulacion

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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    subjects = models.ManyToManyField(Asignatura, blank=True)
    coordinated_titulaciones = models.ManyToManyField(Titulacion, blank=True)

class LoginAttempt(models.Model):
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()

    def __str__(self):
        return f'{self.username} - {self.timestamp} - {"Success" if self.success else "Failed"}'
