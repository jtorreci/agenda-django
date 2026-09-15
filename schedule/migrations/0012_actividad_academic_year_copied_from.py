import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the academic year and import source columns as nullable.

    The year becomes NOT NULL in 0014, after 0013 backfills existing rows. Each
    step is a separate migration so PostgreSQL never alters a column in the same
    transaction that updated its rows.
    """

    dependencies = [
        ('academics', '0006_catalogue_plan_override'),
        ('schedule', '0011_actividad_estado_alter_actividad_activa'),
    ]

    operations = [
        migrations.AddField(
            model_name='actividad',
            name='academic_year',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='activities',
                to='academics.academicyear',
            ),
        ),
        migrations.AddField(
            model_name='actividad',
            name='copied_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='copies',
                to='schedule.actividad',
            ),
        ),
    ]
