from django import forms
from .models import Actividad, ActividadGrupo, VistaCalendario, TipoActividad
from academics.models import Asignatura
import json
import uuid
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import pytz

class LocalDateTimeWidget(forms.DateTimeInput):
    """
    Widget personalizado para manejar datetime-local con timezone correcto.
    Convierte automáticamente entre UTC (BD) y zona horaria local del usuario.
    """

    def __init__(self, attrs=None, format=None):
        default_attrs = {'type': 'datetime-local'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs, format=format or '%Y-%m-%dT%H:%M')

    def format_value(self, value):
        """
        Convierte el valor de la BD (UTC) a timezone local para mostrar en el widget
        """
        if value is None:
            return None

        if isinstance(value, str):
            return value

        # Si el valor viene de la BD (timezone aware), convertir a local
        if timezone.is_aware(value):
            local_tz = pytz.timezone(settings.TIME_ZONE)
            local_time = value.astimezone(local_tz)
            return local_time.strftime(self.format_key)

        # Si no tiene timezone, asumir que ya es local
        return value.strftime(self.format_key)

    @property
    def format_key(self):
        return self.format or '%Y-%m-%dT%H:%M'

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

        # Configure datetime input formats for datetime-local
        self.fields['fecha_inicio'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        self.fields['fecha_fin'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']

        if read_only: # Apply read-only attributes
            for field_name, field in self.fields.items():
                if field_name in ['fecha_inicio', 'fecha_fin']:
                    field.widget.attrs['readonly'] = True
                    # Do NOT set disabled=True for date/time fields if we want their value to show
                else:
                    field.widget.attrs['readonly'] = True
                    field.widget.attrs['disabled'] = True # Disable for checkboxes/selects
                field.required = False # Make fields not required in read-only mode

    def clean_fecha_inicio(self):
        """
        Convierte la fecha de entrada de timezone local a UTC para almacenar en BD
        """
        fecha_inicio = self.cleaned_data.get('fecha_inicio')
        if fecha_inicio:
            return self._localize_datetime(fecha_inicio)
        return fecha_inicio

    def clean_fecha_fin(self):
        """
        Convierte la fecha de entrada de timezone local a UTC para almacenar en BD
        """
        fecha_fin = self.cleaned_data.get('fecha_fin')
        if fecha_fin:
            return self._localize_datetime(fecha_fin)
        return fecha_fin

    def _localize_datetime(self, dt):
        """
        Convierte un datetime naive (de datetime-local) a timezone aware en la zona local,
        luego lo deja que Django lo convierta a UTC automáticamente.
        """
        if dt is None:
            return None

        if timezone.is_naive(dt):
            # El datetime viene del widget como naive, asumimos que es timezone local
            local_tz = pytz.timezone(settings.TIME_ZONE)
            return local_tz.localize(dt)

        return dt

    class Meta:
        model = Actividad
        fields = ['nombre', 'asignaturas', 'tipo_actividad', 'fecha_inicio', 'fecha_fin', 'descripcion', 'evaluable', 'porcentaje_evaluacion', 'no_recuperable']
        widgets = {
            'fecha_inicio': LocalDateTimeWidget(),
            'fecha_fin': LocalDateTimeWidget(),
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

            # Process and localize datetime fields for each group
            for grupo in grupos:
                if not all(k in grupo for k in ['grupo', 'fecha_inicio', 'fecha_fin']):
                    raise forms.ValidationError("Datos de grupo incompletos.")

                # Convert datetime strings to proper timezone-aware datetimes
                if 'fecha_inicio' in grupo and grupo['fecha_inicio']:
                    grupo['fecha_inicio'] = self._parse_and_localize_datetime(grupo['fecha_inicio'])

                if 'fecha_fin' in grupo and grupo['fecha_fin']:
                    grupo['fecha_fin'] = self._parse_and_localize_datetime(grupo['fecha_fin'])

            return grupos
        except json.JSONDecodeError:
            raise forms.ValidationError("Formato de datos inválido.")

    def _parse_and_localize_datetime(self, datetime_str):
        """
        Parse a datetime string from datetime-local input and localize it to the configured timezone
        """
        if not datetime_str:
            return None

        try:
            from datetime import datetime
            # Parse the datetime-local format
            if 'T' in datetime_str:
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
            else:
                dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

            # Localize to the configured timezone
            if timezone.is_naive(dt):
                local_tz = pytz.timezone(settings.TIME_ZONE)
                return local_tz.localize(dt)

            return dt
        except (ValueError, TypeError) as e:
            raise forms.ValidationError(f"Formato de fecha inválido: {datetime_str}")

    def save(self, user=None):
        if not user:
            raise ValueError("Se requiere usuario para guardar la actividad")
            
        grupos_data = self.cleaned_data['grupos_data']
        
        with transaction.atomic():
            # Crear la actividad principal
            actividad = Actividad(
                nombre=self.cleaned_data['nombre'],
                tipo_actividad=self.cleaned_data['tipo_actividad'],
                evaluable=self.cleaned_data['evaluable'],
                porcentaje_evaluacion=self.cleaned_data['porcentaje_evaluacion'],
                no_recuperable=self.cleaned_data['no_recuperable'],
                # Usar campos del primer grupo para compatibilidad temporal
                fecha_inicio=grupos_data[0]['fecha_inicio'],
                fecha_fin=grupos_data[0]['fecha_fin'],
                descripcion=grupos_data[0]['descripcion']
            )
            actividad.save()
            actividad.asignaturas.set(self.cleaned_data['asignaturas'])
            
            # Crear los grupos
            for i, grupo_info in enumerate(grupos_data, 1):
                ActividadGrupo.objects.create(
                    actividad=actividad,
                    nombre_grupo=grupo_info['grupo'],
                    fecha_inicio=grupo_info['fecha_inicio'],
                    fecha_fin=grupo_info['fecha_fin'],
                    descripcion=grupo_info.get('descripcion', ''),
                    lugar=grupo_info.get('lugar', ''),  # Nuevo campo lugar
                    orden=i
                )
            
            return actividad


class UnifiedActivityForm(forms.Form):
    """
    Formulario unificado para crear actividades individuales o multi-grupo
    """
    nombre = forms.CharField(max_length=255, label="Nombre de la actividad")
    asignaturas = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True,
        label="Asignaturas"
    )
    tipo_actividad = forms.ModelChoiceField(
        queryset=TipoActividad.objects.all(),
        label="Tipo de actividad",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    evaluable = forms.BooleanField(required=False, label="Evaluable")
    porcentaje_evaluacion = forms.DecimalField(
        max_digits=5, decimal_places=2, initial=0.0,
        label="Porcentaje de evaluación",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
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
            grupos = json.loads(grupos_data) if grupos_data else []
            if not grupos:
                raise forms.ValidationError("Debe añadir al menos un grupo.")

            # Process and localize datetime fields for each group
            for grupo in grupos:
                if not all(k in grupo for k in ['grupo', 'fecha_inicio', 'fecha_fin']):
                    raise forms.ValidationError("Datos de grupo incompletos.")

                # Convert datetime strings to proper timezone-aware datetimes
                if 'fecha_inicio' in grupo and grupo['fecha_inicio']:
                    grupo['fecha_inicio'] = self._parse_and_localize_datetime(grupo['fecha_inicio'])

                if 'fecha_fin' in grupo and grupo['fecha_fin']:
                    grupo['fecha_fin'] = self._parse_and_localize_datetime(grupo['fecha_fin'])

            return grupos
        except json.JSONDecodeError:
            raise forms.ValidationError("Formato de datos inválido.")

    def _parse_and_localize_datetime(self, datetime_str):
        """
        Parse a datetime string from datetime-local input and localize it to the configured timezone
        """
        if not datetime_str:
            return None

        try:
            from datetime import datetime
            # Parse the datetime-local format
            if 'T' in datetime_str:
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
            else:
                dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

            # Localize to the configured timezone
            if timezone.is_naive(dt):
                local_tz = pytz.timezone(settings.TIME_ZONE)
                return local_tz.localize(dt)

            return dt
        except (ValueError, TypeError) as e:
            raise forms.ValidationError(f"Formato de fecha inválido: {datetime_str}")

    def save(self, user=None):
        if not user:
            raise ValueError("Se requiere usuario para guardar la actividad")
            
        grupos_data = self.cleaned_data['grupos_data']
        
        with transaction.atomic():
            # Crear la actividad principal
            actividad = Actividad(
                nombre=self.cleaned_data['nombre'],
                tipo_actividad=self.cleaned_data['tipo_actividad'],
                evaluable=self.cleaned_data['evaluable'],
                porcentaje_evaluacion=self.cleaned_data['porcentaje_evaluacion'],
                no_recuperable=self.cleaned_data['no_recuperable'],
                # Usar campos del primer grupo para compatibilidad temporal
                fecha_inicio=grupos_data[0]['fecha_inicio'],
                fecha_fin=grupos_data[0]['fecha_fin'],
                descripcion=grupos_data[0].get('descripcion', '')
            )
            actividad.save()
            actividad.asignaturas.set(self.cleaned_data['asignaturas'])
            
            # Crear los grupos
            for i, grupo_info in enumerate(grupos_data, 1):
                ActividadGrupo.objects.create(
                    actividad=actividad,
                    nombre_grupo=grupo_info['grupo'],
                    fecha_inicio=grupo_info['fecha_inicio'],
                    fecha_fin=grupo_info['fecha_fin'],
                    descripcion=grupo_info.get('descripcion', ''),
                    lugar=grupo_info.get('lugar', ''),
                    orden=i
                )
            
            return actividad
