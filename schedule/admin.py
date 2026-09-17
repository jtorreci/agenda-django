from django.contrib import admin
from .models import (
    Actividad,
    IcalImport,
    IcalImportEvent,
    MoodleCourseSubject,
    TipoActividad,
    VistaCalendario,
)

admin.site.register(TipoActividad)
admin.site.register(Actividad)
admin.site.register(VistaCalendario)
admin.site.register(IcalImport)
admin.site.register(IcalImportEvent)
admin.site.register(MoodleCourseSubject)
