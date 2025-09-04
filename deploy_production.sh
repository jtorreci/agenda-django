#!/bin/bash
# Script de despliegue para PythonAnywhere
# Ejecutar este script después de actualizar el código en el servidor

echo "=== Iniciando despliegue en producción ==="

# Activar el entorno virtual si existe
if [ -d "/home/jtorreci/.virtualenvs/agenda-django" ]; then
    source /home/jtorreci/.virtualenvs/agenda-django/bin/activate
    echo "✓ Entorno virtual activado"
fi

# Instalar/actualizar dependencias
echo "→ Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

# Recolectar archivos estáticos
echo "→ Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# Aplicar migraciones
echo "→ Aplicando migraciones..."
python manage.py migrate

# Crear caché de compilación para mejorar rendimiento
echo "→ Compilando archivos Python..."
python -m compileall .

# Verificar la configuración
echo "→ Verificando configuración..."
python manage.py check --deploy

# Reiniciar la aplicación web en PythonAnywhere
echo "→ Reiniciando aplicación web..."
touch /var/www/jtorreci_pythonanywhere_com_wsgi.py

echo "=== Despliegue completado ==="
echo "Nota: Si hay problemas con CSS del admin, ejecutar:"
echo "  python manage.py collectstatic --noinput --clear"
echo "  python manage.py findstatic admin/css/base.css"