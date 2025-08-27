from django import forms
from .models import CustomUser
from academics.models import Asignatura

class NotificationForm(forms.Form):
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)

class StudentSubjectForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Asignatura.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ['subjects']
