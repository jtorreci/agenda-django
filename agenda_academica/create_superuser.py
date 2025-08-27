import os
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
django.setup()

from users.models import CustomUser

if not CustomUser.objects.filter(username='jtorreci').exists():
    call_command('createsuperuser', username='jtorreci', email='jtorreci@unex.es', interactive=False)
    user = CustomUser.objects.get(username='jtorreci')
    user.set_password('T0rr3c1lla')
    user.save()
    print("Superusuario 'jtorreci' creado con la contrasena 'T0rr3c1lla'")
else:
    print("El superusuario 'jtorreci' ya existe.")