#!/bin/bash
# Script de configuración para servidor dedicado con Gunicorn y Nginx

echo "=== Configuración del servidor para agenda-django ==="

# Variables (ajustar según tu servidor)
PROJECT_DIR="/home/jtorreci/agenda/agenda-django"
VENV_DIR="/home/jtorreci/agenda/venv"
USER="jtorreci"

cd $PROJECT_DIR

# 1. Activar entorno virtual
echo "→ Activando entorno virtual..."
source $VENV_DIR/bin/activate

# 2. Instalar dependencias
echo "→ Instalando dependencias..."
pip install --upgrade pip
pip install django gunicorn whitenoise python-dotenv mysqlclient

# 3. Recolectar archivos estáticos (CRÍTICO para el CSS del admin)
echo "→ Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# 4. Verificar que los archivos del admin existen
echo "→ Verificando archivos del admin..."
if [ -d "$PROJECT_DIR/staticfiles/admin" ]; then
    echo "✓ Archivos del admin encontrados"
    ls -la $PROJECT_DIR/staticfiles/admin/css/ | head -5
else
    echo "✗ ERROR: No se encontraron los archivos estáticos del admin"
    echo "  Ejecutar: python manage.py collectstatic --noinput"
fi

# 5. Aplicar migraciones
echo "→ Aplicando migraciones..."
python manage.py migrate

# 6. Verificar permisos
echo "→ Configurando permisos..."
chown -R $USER:www-data $PROJECT_DIR
chmod -R 755 $PROJECT_DIR
chmod -R 775 $PROJECT_DIR/staticfiles
chmod -R 775 $PROJECT_DIR/media

# 7. Crear archivo de configuración de Gunicorn
echo "→ Creando configuración de Gunicorn..."
cat > $PROJECT_DIR/gunicorn_config.py << EOF
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 60
keepalive = 2
preload_app = True
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True
EOF

# 8. Probar la configuración
echo "→ Probando la configuración de Django..."
python manage.py check --deploy

echo "=== Configuración completada ==="
echo ""
echo "Pasos siguientes:"
echo "1. Copiar nginx.conf a /etc/nginx/sites-available/agenda"
echo "2. Crear enlace simbólico: ln -s /etc/nginx/sites-available/agenda /etc/nginx/sites-enabled/"
echo "3. Probar configuración de Nginx: nginx -t"
echo "4. Reiniciar Nginx: systemctl restart nginx"
echo "5. Iniciar Gunicorn: gunicorn agenda_academica.wsgi:application -c gunicorn_config.py"