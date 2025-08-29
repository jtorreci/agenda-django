# Generated manually for activity versioning system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('schedule', '0005_expand_logging_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActividadVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_numero', models.PositiveIntegerField()),
                ('fecha_modificacion', models.DateTimeField(auto_now_add=True)),
                ('comentario_version', models.TextField(blank=True, null=True)),
                ('nombre', models.CharField(max_length=255)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('fecha_inicio', models.DateTimeField()),
                ('fecha_fin', models.DateTimeField()),
                ('evaluable', models.BooleanField(default=False)),
                ('porcentaje_evaluacion', models.DecimalField(decimal_places=2, default=0.0, max_digits=5)),
                ('no_recuperable', models.BooleanField(default=False)),
                ('aprobada', models.BooleanField(default=False)),
                ('activa', models.BooleanField(default=True)),
                ('asignaturas_snapshot', models.JSONField(default=list)),
                ('tipo_actividad_snapshot', models.JSONField(default=dict)),
                ('actividad_original', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versiones', to='schedule.actividad')),
                ('modificada_por', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-fecha_modificacion'],
            },
        ),
        migrations.AddConstraint(
            model_name='actividadversion',
            constraint=models.UniqueConstraint(fields=('actividad_original', 'version_numero'), name='unique_activity_version'),
        ),
    ]