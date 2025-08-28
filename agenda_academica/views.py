from django.shortcuts import render, redirect
from .models import AgendaSettings
from .forms import AgendaSettingsForm
from django.contrib.auth.decorators import user_passes_test
from users.views import is_admin
from django.contrib.auth.forms import AuthenticationForm

def home(request):
    form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

def logout_success(request):
    return render(request, 'logout_success.html')

@user_passes_test(is_admin)
def agenda_settings(request):
    settings = AgendaSettings.load()
    if request.method == 'POST':
        form = AgendaSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            return redirect('agenda_settings')
    else:
        form = AgendaSettingsForm(instance=settings)
    return render(request, 'agenda_academica/agenda_settings.html', {'form': form})
