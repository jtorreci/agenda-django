from datetime import date

from django.db import migrations

LEGACY_YEAR_CODE = '2025-26'


def assign_legacy_year(apps, schema_editor):
    """Assign every activity without a year to the archived 2025-26 year.

    All activities that predate academic years were created in 2025-26. The year
    is only created when there is something to backfill, so an empty database
    (e.g. the test database) gets no phantom year.
    """
    Actividad = apps.get_model('schedule', 'Actividad')
    AcademicYear = apps.get_model('academics', 'AcademicYear')

    pending = Actividad.objects.filter(academic_year__isnull=True)
    if not pending.exists():
        return

    year, created = AcademicYear.objects.get_or_create(
        code=LEGACY_YEAR_CODE,
        defaults={
            'starts_on': date(2025, 9, 1),
            'ends_on': date(2026, 8, 31),
            'state': 'archived',
        },
    )
    if not created and year.state == 'draft':
        # A draft year is not browsable; an existing active/archived state is kept.
        year.state = 'archived'
        year.save(update_fields=['state'])

    pending.update(academic_year=year)


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0006_catalogue_plan_override'),
        ('schedule', '0012_actividad_academic_year_copied_from'),
    ]

    operations = [
        # Reversing keeps the assignments; 0012's reverse drops the column anyway.
        migrations.RunPython(assign_legacy_year, migrations.RunPython.noop),
    ]
