from django import forms
from .models import Actividad, VistaCalendario, TipoActividad
from academics.models import Asignatura
import json
import uuid

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

class MultiGroupActivityForm(forms.Form):
    nombre = forms.CharField(max_length=255, label="Nombre de la actividad")
    asignaturas = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Asignaturas"
    )
    tipo_actividad = forms.ModelChoiceField(
        queryset=TipoActividad.objects.all(),
        label="Tipo de actividad"
    )
    evaluable = forms.BooleanField(required=False, label="Evaluable")
    porcentaje_evaluacion = forms.DecimalField(
        max_digits=5, decimal_places=2, initial=0.0,
        label="Porcentaje de evaluación"
    )
    no_recuperable = forms.BooleanField(required=False, label="No recuperable")
    
    grupos_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="Datos JSON de los grupos"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        initial_groups = kwargs.pop('initial_groups', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role in ['TEACHER', 'COORDINATOR', 'ADMIN']:
            self.fields['asignaturas'].queryset = user.subjects.all()
        
        if initial_groups:
            self.fields['grupos_data'].initial = json.dumps(initial_groups)

    def clean_grupos_data(self):
        grupos_data = self.cleaned_data.get('grupos_data', '[]')
        try:
            grupos = json.loads(grupos_data)
            if not grupos:
                raise forms.ValidationError("Debe añadir al menos un grupo.")
            
            for grupo in grupos:
                if not all(k in grupo for k in ['grupo', 'fecha_inicio', 'fecha_fin', 'descripcion']):
                    raise forms.ValidationError("Datos de grupo incompletos.")
                    
            return grupos
        except json.JSONDecodeError:
            raise forms.ValidationError("Formato de datos inválido.")

    def save(self, user=None):
        if not user:
            raise ValueError("Se requiere usuario para guardar la actividad")
            
        grupos_data = self.cleaned_data['grupos_data']
        grupo_id = uuid.uuid4()
        actividades_creadas = []
        
        for grupo_info in grupos_data:
            actividad = Actividad(
                nombre=self.cleaned_data['nombre'],
                tipo_actividad=self.cleaned_data['tipo_actividad'],
                fecha_inicio=grupo_info['fecha_inicio'],
                fecha_fin=grupo_info['fecha_fin'],
                descripcion=f"Grupo {grupo_info['grupo']}: {grupo_info['descripcion']}",
                evaluable=self.cleaned_data['evaluable'],
                porcentaje_evaluacion=self.cleaned_data['porcentaje_evaluacion'],
                no_recuperable=self.cleaned_data['no_recuperable'],
                grupo_id=grupo_id
            )
            actividad.save()
            actividad.asignaturas.set(self.cleaned_data['asignaturas'])
            actividades_creadas.append(actividad)
            
        return actividades_creadas
