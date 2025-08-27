from django import forms
from .models import Actividad, VistaCalendario, TipoActividad
from academics.models import Asignatura

class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = ['nombre', 'asignatura', 'tipo_actividad', 'fecha_inicio', 'fecha_fin', 'descripcion']
        widgets = {
            'asignatura': forms.HiddenInput(),
        }

class VistaCalendarioForm(forms.ModelForm):
    asignaturas = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    tipos_actividad = forms.ModelMultipleChoiceField(
        queryset=TipoActividad.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = VistaCalendario
        fields = ['nombre', 'asignaturas', 'tipos_actividad']
