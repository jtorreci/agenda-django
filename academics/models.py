from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q


class NoActiveAcademicYear(Exception):
    """Raised when an operation needs the active academic year and none exists."""

    default_message = 'No hay ningún curso académico activo. Contacta con la administración.'

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


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

    @classmethod
    def get_active(cls):
        """Return the active academic year, or None when no year is active."""
        return cls.objects.filter(state=cls.STATE_ACTIVE).first()

    @classmethod
    def require_active(cls):
        active = cls.get_active()
        if active is None:
            raise NoActiveAcademicYear()
        return active

    @classmethod
    def selectable(cls):
        """Years users may browse: every non-draft year, newest first."""
        return cls.objects.exclude(state=cls.STATE_DRAFT).order_by('-starts_on')

    @property
    def is_active(self):
        return self.state == self.STATE_ACTIVE

    def clean(self):
        if self.ends_on <= self.starts_on:
            raise ValidationError({'ends_on': 'The academic year must end after it starts.'})

    def missing_offering_metadata(self):
        return self.offerings.filter(
            Q(curricular_year__isnull=True) | Q(semester__isnull=True)
        )

    def activate(self):
        """Activate this draft year, archiving the previously active one atomically."""
        with transaction.atomic():
            locked = AcademicYear.objects.select_for_update().get(pk=self.pk)
            if locked.state != self.STATE_DRAFT:
                raise ValidationError('Only a draft academic year can be activated.')
            if not self.offerings.exists():
                raise ValidationError('An academic year needs at least one subject offering before activation.')
            if self.missing_offering_metadata().exists():
                raise ValidationError('Every offering needs a curricular year and semester before activation.')
            AcademicYear.objects.select_for_update().filter(state=self.STATE_ACTIVE).exclude(pk=self.pk).update(
                state=self.STATE_ARCHIVED
            )
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

class PlanCodeAlias(models.Model):
    """Secondary official plan code (e.g. a mention) grouped into a Titulacion."""

    code = models.CharField(max_length=32, unique=True)
    titulacion = models.ForeignKey(Titulacion, on_delete=models.CASCADE, related_name='plan_code_aliases')
    name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} → {self.titulacion}'


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


def offered_subjects(academic_year, subjects=None):
    """Subjects with an 'offered' SubjectOffering in ``academic_year``.

    ``subjects`` optionally narrows the base queryset (e.g. a user's subjects).
    Returns an empty queryset when ``academic_year`` is None.
    """
    base = Asignatura.objects.all() if subjects is None else subjects
    if academic_year is None:
        return base.none()
    offered_ids = SubjectOffering.objects.filter(
        academic_year=academic_year, state=SubjectOffering.STATE_OFFERED
    ).values('subject_id')
    return base.filter(id__in=offered_ids)


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


class CatalogueImport(models.Model):
    STATE_DRAFT = 'draft'
    STATE_APPLIED = 'applied'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Draft'),
        (STATE_APPLIED, 'Applied'),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='catalogue_imports')
    source_filename = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        'users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='catalogue_imports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_DRAFT)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def incomplete_rows(self):
        return self.rows.filter(Q(curricular_year__isnull=True) | Q(semester__isnull=True))

    def __str__(self):
        return f'{self.academic_year} · {self.source_filename} ({self.state})'


class CatalogueImportRow(models.Model):
    MATCH_CODE = 'code'
    MATCH_NAME = 'name'
    MATCH_NEW = 'new'
    MATCH_MANUAL = 'manual'
    MATCH_CHOICES = [
        (MATCH_CODE, 'Matched by code'),
        (MATCH_NAME, 'Matched by name'),
        (MATCH_NEW, 'New'),
        (MATCH_MANUAL, 'Manual mapping'),
    ]

    catalogue_import = models.ForeignKey(CatalogueImport, on_delete=models.CASCADE, related_name='rows')
    line_number = models.PositiveIntegerField(null=True, blank=True)
    plan_code = models.CharField(max_length=32)
    plan_name = models.CharField(max_length=255)
    subject_code = models.CharField(max_length=32)
    subject_name = models.CharField(max_length=255)
    credits = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    curricular_year = models.PositiveSmallIntegerField(null=True, blank=True)
    semester = models.PositiveSmallIntegerField(null=True, blank=True)
    target_titulacion = models.ForeignKey(
        Titulacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    target_asignatura = models.ForeignKey(
        Asignatura, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    ROLE_PRIMARY = 'primary'
    ROLE_ALIAS = 'alias'
    ROLE_CHOICES = [
        (ROLE_PRIMARY, 'Primary plan code'),
        (ROLE_ALIAS, 'Alias plan code'),
    ]

    match_status = models.CharField(max_length=10, choices=MATCH_CHOICES, default=MATCH_NEW)
    plan_match_status = models.CharField(max_length=10, choices=MATCH_CHOICES, default=MATCH_NEW)
    plan_role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_PRIMARY)
    plan_group = models.CharField(
        max_length=64,
        blank=True,
        help_text='Rows sharing this key land in the same Titulacion: "t:<pk>" or "new:<primary plan code>".',
    )

    class Meta:
        ordering = ['plan_code', 'curricular_year', 'semester', 'subject_code']
        constraints = [
            models.UniqueConstraint(
                fields=['catalogue_import', 'plan_code', 'subject_code'],
                name='academics_unique_catalogue_import_row',
            )
        ]

    @property
    def is_complete(self):
        return self.curricular_year is not None and self.semester is not None

    def __str__(self):
        return f'{self.plan_code}/{self.subject_code} {self.subject_name}'


class CatalogueImportPlanOverride(models.Model):
    """Admin-chosen mapping of one plan code in a draft import.

    ``titulacion`` set: the plan code lands in that Titulacion.
    ``titulacion`` null: force a new Titulacion even if the name matches.
    Deleting the Titulacion deletes the override (back to automatic).
    """

    catalogue_import = models.ForeignKey(CatalogueImport, on_delete=models.CASCADE, related_name='plan_overrides')
    plan_code = models.CharField(max_length=32)
    titulacion = models.ForeignKey(
        Titulacion, on_delete=models.CASCADE, null=True, blank=True, related_name='+'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['catalogue_import', 'plan_code'],
                name='academics_unique_catalogue_plan_override',
            )
        ]

    def __str__(self):
        return f'{self.catalogue_import_id} · {self.plan_code} → {self.titulacion or "new"}'
