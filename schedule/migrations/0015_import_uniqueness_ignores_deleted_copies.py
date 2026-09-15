from django.db import migrations, models


class Migration(migrations.Migration):
    """Deleted copies no longer block re-importing the same source into a year."""

    dependencies = [
        ('schedule', '0014_actividad_academic_year_not_null'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='actividad',
            name='schedule_unique_activity_import_per_year',
        ),
        migrations.AddConstraint(
            model_name='actividad',
            constraint=models.UniqueConstraint(
                condition=models.Q(('copied_from__isnull', False), ('estado', 'visible')),
                fields=('copied_from', 'academic_year'),
                name='schedule_unique_activity_import_per_year',
            ),
        ),
    ]
