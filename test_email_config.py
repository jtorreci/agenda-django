#!/usr/bin/env python
"""
Script para probar diferentes configuraciones de email SMTP
Ejecutar desde el directorio del proyecto Django con el entorno virtual activado
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import sys
import os
import django

# Configurar Django
sys.path.append('/home/jtorreci/agenda/agenda-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
django.setup()

# Configuraciones a probar
CONFIGURATIONS = [
    {
        'name': 'Config 1: TLS puerto 587 con usuario completo',
        'host': 'mailout.unex.es',
        'port': 587,
        'use_tls': True,
        'use_ssl': False,
        'username': 'secretaria_epcc@unex.es',
        'password': 'cZiFs4XQna',
        'from_email': 'secretaria_epcc@unex.es'
    },
    {
        'name': 'Config 2: TLS puerto 587 con usuario sin dominio',
        'host': 'mailout.unex.es',
        'port': 587,
        'use_tls': True,
        'use_ssl': False,
        'username': 'secretaria_epcc',
        'password': 'cZiFs4XQna',
        'from_email': 'secretaria_epcc@unex.es'
    },
    {
        'name': 'Config 3: SSL puerto 465 con usuario completo',
        'host': 'mailout.unex.es',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
        'username': 'secretaria_epcc@unex.es',
        'password': 'cZiFs4XQna',
        'from_email': 'secretaria_epcc@unex.es'
    },
    {
        'name': 'Config 4: SSL puerto 465 con usuario sin dominio',
        'host': 'mailout.unex.es',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
        'username': 'secretaria_epcc',
        'password': 'cZiFs4XQna',
        'from_email': 'secretaria_epcc@unex.es'
    },
    {
        'name': 'Config 5: Sin cifrado puerto 25 con usuario sin dominio',
        'host': 'mailout.unex.es',
        'port': 25,
        'use_tls': False,
        'use_ssl': False,
        'username': 'secretaria_epcc',
        'password': 'cZiFs4XQna',
        'from_email': 'secretaria_epcc@unex.es'
    }
]

# Email de destino
TO_EMAIL = 'jtorreci@unex.es'

def test_smtp_connection(config):
    """Prueba una configuración SMTP específica"""
    print(f"\n{'='*60}")
    print(f"Probando: {config['name']}")
    print(f"{'='*60}")
    print(f"Host: {config['host']}:{config['port']}")
    print(f"Usuario: {config['username']}")
    print(f"TLS: {config['use_tls']}, SSL: {config['use_ssl']}")
    
    try:
        # Crear conexión según el tipo
        if config['use_ssl']:
            print("→ Conectando con SSL...")
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(config['host'], config['port'], context=context)
        else:
            print("→ Conectando sin SSL...")
            server = smtplib.SMTP(config['host'], config['port'])
            server.set_debuglevel(1)  # Activar debug
            
            if config['use_tls']:
                print("→ Iniciando STARTTLS...")
                context = ssl.create_default_context()
                server.starttls(context=context)
        
        # Intentar login
        print("→ Autenticando...")
        server.login(config['username'], config['password'])
        print("✓ Autenticación exitosa")
        
        # Preparar mensaje
        message = MIMEMultipart()
        message['From'] = config['from_email']
        message['To'] = TO_EMAIL
        message['Subject'] = f"Test Email - {config['name']}"
        
        body = f"""
Este es un email de prueba desde la Agenda Académica.

CONFIGURACIÓN UTILIZADA:
========================
{config['name']}
Host: {config['host']}
Puerto: {config['port']}
Usuario: {config['username']}
TLS: {config['use_tls']}
SSL: {config['use_ssl']}
Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Si recibes este mensaje, esta configuración funciona correctamente.

Saludos,
Sistema de Agenda Académica
        """
        
        message.attach(MIMEText(body, 'plain'))
        
        # Enviar email
        print(f"→ Enviando email a {TO_EMAIL}...")
        result = server.send_message(message)
        print(f"✓ Email enviado exitosamente")
        
        server.quit()
        
        return True, "Éxito"
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"✗ Error de autenticación: {str(e)}"
        print(error_msg)
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"✗ Error SMTP: {str(e)}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"✗ Error general: {str(e)}"
        print(error_msg)
        return False, error_msg

def test_django_email(config):
    """Prueba usando la configuración de Django directamente"""
    print(f"\n→ Probando con Django send_mail...")
    
    # Configurar Django temporalmente
    from django.conf import settings
    from django.core.mail import send_mail
    
    # Guardar configuración original
    original_host = getattr(settings, 'EMAIL_HOST', None)
    original_port = getattr(settings, 'EMAIL_PORT', None)
    original_use_tls = getattr(settings, 'EMAIL_USE_TLS', None)
    original_use_ssl = getattr(settings, 'EMAIL_USE_SSL', None)
    original_user = getattr(settings, 'EMAIL_HOST_USER', None)
    original_password = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
    
    try:
        # Aplicar configuración de prueba
        settings.EMAIL_HOST = config['host']
        settings.EMAIL_PORT = config['port']
        settings.EMAIL_USE_TLS = config['use_tls']
        settings.EMAIL_USE_SSL = config['use_ssl']
        settings.EMAIL_HOST_USER = config['username']
        settings.EMAIL_HOST_PASSWORD = config['password']
        settings.DEFAULT_FROM_EMAIL = config['from_email']
        
        result = send_mail(
            f"Django Test - {config['name']}",
            f"Email enviado con Django usando:\n{config['name']}\n\nFecha: {datetime.now()}",
            config['from_email'],
            [TO_EMAIL],
            fail_silently=False
        )
        print(f"✓ Django send_mail exitoso. Emails enviados: {result}")
        return True
        
    except Exception as e:
        print(f"✗ Error con Django send_mail: {str(e)}")
        return False
    finally:
        # Restaurar configuración original
        settings.EMAIL_HOST = original_host
        settings.EMAIL_PORT = original_port
        settings.EMAIL_USE_TLS = original_use_tls
        settings.EMAIL_USE_SSL = original_use_ssl
        settings.EMAIL_HOST_USER = original_user
        settings.EMAIL_HOST_PASSWORD = original_password

def main():
    print("\n" + "="*60)
    print("PRUEBA DE CONFIGURACIONES DE EMAIL SMTP")
    print("="*60)
    print(f"Destinatario: {TO_EMAIL}")
    print(f"Hora de inicio: {datetime.now()}")
    
    results = []
    
    for config in CONFIGURATIONS:
        # Probar conexión SMTP directa
        success, message = test_smtp_connection(config)
        
        # Si funciona, probar también con Django
        if success:
            django_success = test_django_email(config)
            results.append({
                'config': config['name'],
                'smtp': 'Éxito',
                'django': 'Éxito' if django_success else 'Fallo'
            })
        else:
            results.append({
                'config': config['name'],
                'smtp': 'Fallo',
                'django': 'No probado'
            })
    
    # Resumen final
    print("\n" + "="*60)
    print("RESUMEN DE RESULTADOS")
    print("="*60)
    
    for result in results:
        status = "✓" if result['smtp'] == 'Éxito' else "✗"
        print(f"{status} {result['config']}")
        print(f"   SMTP: {result['smtp']} | Django: {result['django']}")
    
    # Guardar resultados en archivo
    with open('email_test_results.txt', 'w') as f:
        f.write(f"Resultados de pruebas de email - {datetime.now()}\n")
        f.write("="*60 + "\n\n")
        for result in results:
            f.write(f"{result['config']}\n")
            f.write(f"SMTP: {result['smtp']} | Django: {result['django']}\n\n")
    
    print(f"\nResultados guardados en: email_test_results.txt")
    
    # Mostrar configuración recomendada
    successful = [r for r in results if r['smtp'] == 'Éxito' and r['django'] == 'Éxito']
    if successful:
        print(f"\n✓ CONFIGURACIÓN RECOMENDADA: {successful[0]['config']}")
    else:
        print("\n✗ Ninguna configuración funcionó completamente")

if __name__ == "__main__":
    main()