from django import forms
from .models import Actividad, VistaCalendario, TipoActividad
from academics.models import Asignatura

class ActividadForm(forms.ModelForm):
    asignaturas = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.none(), # Set initial queryset to none
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Asignaturas"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        read_only = kwargs.pop('read_only', False) # New parameter
        # Set queryset before calling super().__init__
        if user and user.role in ['TEACHER', 'COORDINATOR', 'ADMIN']:
            self.base_fields['asignaturas'].queryset = user.subjects.all()
        super().__init__(*args, **kwargs)

        if read_only: # Apply read-only attributes
            for field_name, field in self.fields.items():
                if field_name in ['fecha_inicio', 'fecha_fin']:
                    field.widget.attrs['readonly'] = True
                    # Do NOT set disabled=True for date/time fields if we want their value to show
                else:
                    field.widget.attrs['readonly'] = True
                    field.widget.attrs['disabled'] = True # Disable for checkboxes/selects
                field.required = False # Make fields not required in read-only mode

    class Meta:
        model = Actividad
        fields = ['nombre', 'asignaturas', 'tipo_actividad', 'fecha_inicio', 'fecha_fin', 'descripcion', 'evaluable', 'porcentaje_evaluacion', 'no_recuperable']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class VistaCalendarioForm(forms.ModelForm):
    asignaturas = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.none(), # Set initial queryset to none
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    tipos_actividad = forms.ModelMultipleChoiceField(
        queryset=TipoActividad.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            if user.role in ['TEACHER', 'COORDINATOR', 'ADMIN']:
                self.fields['asignaturas'].queryset = user.subjects.all()
            elif user.role == 'STUDENT':
                self.fields['asignaturas'].queryset = Asignatura.objects.all()

    class Meta:
        model = VistaCalendario
        fields = ['nombre', 'asignaturas', 'tipos_actividad']
