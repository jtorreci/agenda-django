from django.db import models
from django.utils import timezone

class AgendaSettings(models.Model):
    closing_date = models.DateField('fecha de cierre')

    class Meta:
        verbose_name = 'configuración de la agenda'
        verbose_name_plural = 'configuración de la agenda'

    def save(self, *args, **kwargs):
        self.pk = 1
        super(AgendaSettings, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1, defaults={'closing_date': timezone.now().date()})
        return obj