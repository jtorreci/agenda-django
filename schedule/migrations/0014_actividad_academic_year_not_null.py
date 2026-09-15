import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0006_catalogue_plan_override'),
        ('schedule', '0013_backfill_activity_academic_year'),
    ]

    operations = [
        migrations.AlterField(
            model_name='actividad',
            name='academic_year',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='activities',
                to='academics.academicyear',
            ),
        ),
        migrations.AddConstraint(
            model_name='actividad',
            constraint=models.UniqueConstraint(
                condition=models.Q(('copied_from__isnull', False)),
                fields=('copied_from', 'academic_year'),
                name='schedule_unique_activity_import_per_year',
            ),
        ),
    ]
