import re

from django import forms

from .models import AcademicYear

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
YEAR_CODE_PATTERN = re.compile(r'^(\d{4})-(\d{2})$')


class CatalogueUploadForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.exclude(state=AcademicYear.STATE_ARCHIVED),
        required=False,
        label='Curso académico existente',
        empty_label='— Crear un curso académico nuevo —',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    new_year_code = forms.CharField(
        required=False,
        max_length=9,
        label='Código del curso académico nuevo',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2026-27'}),
    )
    new_year_starts_on = forms.DateField(
        required=False,
        label='Inicio',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
    )
    new_year_ends_on = forms.DateField(
        required=False,
        label='Fin',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
    )
    file = forms.FileField(
        label='Fichero CSV del catálogo',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,text/csv'}),
    )

    def clean_new_year_code(self):
        code = self.cleaned_data['new_year_code'].strip()
        if not code:
            return code
        match = YEAR_CODE_PATTERN.match(code)
        if not match or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
            raise forms.ValidationError('Use el formato AAAA-AA con años consecutivos, por ejemplo 2026-27.')
        if AcademicYear.objects.filter(code=code).exists():
            raise forms.ValidationError('Ya existe un curso académico con ese código.')
        return code

    def clean_file(self):
        upload = self.cleaned_data['file']
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError('El fichero supera el tamaño máximo de 5 MB.')
        return upload

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get('academic_year')
        code = cleaned.get('new_year_code')
        starts_on = cleaned.get('new_year_starts_on')
        ends_on = cleaned.get('new_year_ends_on')
        if year and (code or starts_on or ends_on):
            raise forms.ValidationError('Elija un curso académico existente o cree uno nuevo, no ambas cosas.')
        if not year and 'new_year_code' not in self.errors:
            if not (code and starts_on and ends_on):
                raise forms.ValidationError('Elija un curso académico existente o indique código, inicio y fin del curso académico nuevo.')
            if ends_on <= starts_on:
                self.add_error('new_year_ends_on', 'El curso académico debe terminar después de empezar.')
        return cleaned
