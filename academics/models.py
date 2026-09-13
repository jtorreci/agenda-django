from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class AcademicYear(models.Model):
    STATE_DRAFT = 'draft'
    STATE_ACTIVE = 'active'
    STATE_ARCHIVED = 'archived'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Draft'),
        (STATE_ACTIVE, 'Active'),
        (STATE_ARCHIVED, 'Archived'),
    ]

    code = models.CharField(max_length=9, unique=True, help_text='Example: 2026-27')
    starts_on = models.DateField()
    ends_on = models.DateField()
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_DRAFT)

    class Meta:
        ordering = ['-starts_on']
        constraints = [
            models.UniqueConstraint(
                fields=['state'],
                condition=Q(state='active'),
                name='academics_single_active_year',
            )
        ]

    def clean(self):
        if self.ends_on <= self.starts_on:
            raise ValidationError({'ends_on': 'The academic year must end after it starts.'})

    def missing_offering_metadata(self):
        return self.offerings.filter(
            Q(curricular_year__isnull=True) | Q(semester__isnull=True)
        )

    def activate(self):
        if self.missing_offering_metadata().exists():
            raise ValidationError('Every offering needs a curricular year and semester before activation.')
        self.state = self.STATE_ACTIVE
        self.full_clean()
        self.save(update_fields=['state'])

    def __str__(self):
        return self.code

class Titulacion(models.Model):
    nombre = models.CharField(max_length=255)
    codigo_plan = models.CharField(max_length=32, blank=True, null=True, unique=True)
    coordinador = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='coordinated_titulaciones_as_coordinator')

    def __str__(self):
        return self.nombre

class Asignatura(models.Model):
    nombre = models.CharField(max_length=255)
    codigo_asignatura = models.CharField(max_length=32, blank=True, null=True)
    titulacion = models.ForeignKey(Titulacion, on_delete=models.CASCADE)
    curso = models.IntegerField()
    semestre = models.IntegerField()
    coordinator = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='coordinated_subjects') # New field

    def __str__(self):
        return self.nombre

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['titulacion', 'codigo_asignatura'],
                name='academics_unique_subject_code_per_plan',
            )
        ]


class SubjectOffering(models.Model):
    STATE_OFFERED = 'offered'
    STATE_WITHDRAWN = 'withdrawn'
    STATE_CHOICES = [
        (STATE_OFFERED, 'Offered'),
        (STATE_WITHDRAWN, 'Withdrawn'),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='offerings')
    subject = models.ForeignKey(Asignatura, on_delete=models.PROTECT, related_name='offerings')
    curricular_year = models.PositiveSmallIntegerField(null=True, blank=True)
    semester = models.PositiveSmallIntegerField(null=True, blank=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_OFFERED)

    class Meta:
        ordering = ['academic_year', 'subject__titulacion__nombre', 'curricular_year', 'semester', 'subject__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'subject'],
                name='academics_unique_subject_offering_per_year',
            )
        ]

    def __str__(self):
        return f'{self.academic_year} · {self.subject}'


class TeachingAssignment(models.Model):
    teacher = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='teaching_assignments')
    offering = models.ForeignKey(SubjectOffering, on_delete=models.CASCADE, related_name='teaching_assignments')
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'offering'],
                name='academics_unique_teacher_offering',
            )
        ]

    def __str__(self):
        return f'{self.teacher} · {self.offering}'
