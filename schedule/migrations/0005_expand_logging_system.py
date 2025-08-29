# Manual migration for expanding LogActividad to support multiple object types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0004_actividad_activa_actividad_aprobada_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='logactividad',
            name='object_type',
            field=models.CharField(
                choices=[('actividad', 'Activity'), ('tipo_actividad', 'Activity Type'), ('coordinador', 'Coordinator Assignment')],
                default='actividad',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='logactividad',
            name='object_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='logactividad',
            name='object_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='logactividad',
            name='details',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='logactividad',
            name='actividad',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to='schedule.actividad'),
        ),
        migrations.AlterModelOptions(
            name='logactividad',
            options={'ordering': ['-timestamp']},
        ),
    ]