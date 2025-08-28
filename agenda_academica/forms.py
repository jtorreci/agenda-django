from django import forms
from .models import AgendaSettings

class AgendaSettingsForm(forms.ModelForm):
    class Meta:
        model = AgendaSettings
        fields = ['closing_date']
        widgets = {
            'closing_date': forms.DateInput(attrs={'type': 'date'}),
        }