from django.shortcuts import render, redirect
from .models import AgendaSettings
from .forms import AgendaSettingsForm
from django.contrib.auth.decorators import user_passes_test, login_required
from users.views import is_admin
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime

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

@login_required
@user_passes_test(lambda u: u.role == 'ADMIN' or u.is_superuser)
@require_http_methods(["PUT"])
def ajax_update_agenda_settings(request):
    try:
        data = json.loads(request.body)
        closing_date_str = data.get('closing_date', '').strip()
        
        if not closing_date_str:
            return JsonResponse({'success': False, 'error': 'La fecha de cierre es requerida'})
        
        # Parse the date string (expecting YYYY-MM-DD format from HTML5 date input)
        try:
            closing_date = datetime.strptime(closing_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Formato de fecha inválido. Use YYYY-MM-DD'})
        
        # Load and update settings
        settings = AgendaSettings.load()
        settings.closing_date = closing_date
        settings.save()
        
        return JsonResponse({
            'success': True,
            'closing_date': closing_date.strftime('%Y-%m-%d'),
            'closing_date_display': closing_date.strftime('%d/%m/%Y')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON inválidos'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
