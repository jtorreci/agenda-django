# 🚀 **GUÍA COMPLETA DE DESPLIEGUE AL SERVIDOR**

## 📋 **ANÁLISIS DE CAMBIOS REALIZADOS**

### **Cambios en Modelos:**
1. **Nuevo modelo `ActividadGrupo`**:
   - Tabla: `schedule_actividadgrupo`
   - Campos: `actividad`, `nombre_grupo`, `fecha_inicio`, `fecha_fin`, `descripcion`, `lugar`, `orden`
   - Constraint: `unique_together = ['actividad', 'nombre_grupo']`

2. **Modelo `Actividad` modificado**:
   - Nuevo campo: `related_name='grupos'` para ActividadGrupo
   - Campo `grupo_id` marcado como `DEPRECATED`
   - Nuevas propiedades: `grupos_count`, `primer_grupo`

### **Cambios en Views:**
3. **Nuevo sistema unificado**:
   - `UnifiedActivityForm` y `unified_activity_form.html`
   - Views: `unified_activity_form`, funciones de copia actualizadas
   - `get_filtered_activities` modificado para manejar multi-grupo

### **Migraciones a aplicar:**
4. **Migraciones generadas**:
   - `0010_merge_20250916_1149.py` (fusiona conflictos)
   - Crea tabla `schedule_actividadgrupo`
   - Modifica campo `grupo_id` en `actividad`

---

## 🔧 **PASOS DE DESPLIEGUE AL SERVIDOR**

### **PASO 1: Preparación y Backup**

```bash
# 1. Conectar al servidor
ssh usuario@servidor

# 2. Navegar al directorio del proyecto
cd /home/jtorreci/agenda/agenda-django

# 3. CREAR BACKUP COMPLETO DE LA BASE DE DATOS
sudo -u postgres pg_dump -h localhost -p 5432 -U postgres -W agenda_db > /home/jtorreci/backups/agenda_db_backup_$(date +%Y%m%d_%H%M%S).sql

# 4. Crear backup de archivos estáticos
cp -r staticfiles staticfiles_backup_$(date +%Y%m%d_%H%M%S)

# 5. Verificar que el backup se creó correctamente
ls -la /home/jtorreci/backups/
```

### **PASO 2: Actualización de Código**

```bash
# 1. Desactivar el servidor temporalmente (opcional)
sudo systemctl stop gunicorn

# 2. Hacer stash de cambios locales si los hay
git stash

# 3. Obtener los últimos cambios
git pull origin master

# 4. Verificar que no hay archivos .pyc problemáticos
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# 5. Instalar/actualizar dependencias si hay cambios
pip install -r requirements.txt
```

### **PASO 3: Aplicar Migraciones**

```bash
# 1. Verificar migraciones pendientes
python manage.py showmigrations

# 2. Hacer una migración en seco para verificar
python manage.py migrate --dry-run

# 3. Aplicar migraciones
python manage.py migrate

# 4. Verificar que las migraciones se aplicaron correctamente
python manage.py showmigrations schedule
```

### **PASO 4: Actualizar Archivos Estáticos**

```bash
# 1. Recolectar archivos estáticos
python manage.py collectstatic --noinput

# 2. Verificar permisos
sudo chown -R www-data:www-data staticfiles/
```

### **PASO 5: Verificación y Reinicio**

```bash
# 1. Verificar que Django funciona
python manage.py check

# 2. Reiniciar servicios
sudo systemctl start gunicorn
sudo systemctl restart nginx

# 3. Verificar estado de servicios
sudo systemctl status gunicorn
sudo systemctl status nginx

# 4. Comprobar logs
sudo tail -f /var/log/gunicorn/error.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🔄 **ESTRATEGIA DE ROLLBACK SEGURO**

### **ROLLBACK RÁPIDO (Si el sitio no carga)**

```bash
# 1. Parar servicios
sudo systemctl stop gunicorn

# 2. Revertir al commit anterior
git reset --hard HEAD~1

# 3. Restaurar base de datos desde backup
sudo -u postgres psql -h localhost -p 5432 -U postgres -d agenda_db < /home/jtorreci/backups/agenda_db_backup_YYYYMMDD_HHMMSS.sql

# 4. Restaurar archivos estáticos
rm -rf staticfiles
mv staticfiles_backup_YYYYMMDD_HHMMSS staticfiles

# 5. Reiniciar servicios
sudo systemctl start gunicorn
sudo systemctl restart nginx
```

### **ROLLBACK DE MIGRACIONES ESPECÍFICAS**

```bash
# 1. Ver migraciones aplicadas
python manage.py showmigrations schedule

# 2. Revertir migración específica (ej: volver a 0007)
python manage.py migrate schedule 0007

# 3. Eliminar archivos de migración problemáticos
rm schedule/migrations/0008_*.py
rm schedule/migrations/0009_*.py  
rm schedule/migrations/0010_*.py

# 4. Verificar estado
python manage.py showmigrations
```

---

## 💾 **PROCEDIMIENTOS DE BACKUP**

### **BACKUP AUTOMÁTICO DIARIO (Agregar a crontab)**

```bash
# Editar crontab
crontab -e

# Añadir línea para backup diario a las 2 AM
0 2 * * * /home/jtorreci/backup_daily.sh
```

**Crear script `/home/jtorreci/backup_daily.sh`:**

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/jtorreci/backups"
PROJECT_DIR="/home/jtorreci/agenda/agenda-django"

# Crear directorio si no existe
mkdir -p $BACKUP_DIR

# Backup de base de datos
sudo -u postgres pg_dump -h localhost -p 5432 -U postgres agenda_db > $BACKUP_DIR/agenda_db_daily_$DATE.sql

# Backup de archivos de código
tar -czf $BACKUP_DIR/agenda_code_$DATE.tar.gz $PROJECT_DIR

# Limpiar backups antiguos (mantener solo últimos 7 días)
find $BACKUP_DIR -name "agenda_db_daily_*" -mtime +7 -delete
find $BACKUP_DIR -name "agenda_code_*" -mtime +7 -delete

# Log del backup
echo "$(date): Backup completado - $DATE" >> $BACKUP_DIR/backup.log
```

**Hacer el script ejecutable:**
```bash
chmod +x /home/jtorreci/backup_daily.sh
```

### **BACKUP MANUAL ANTES DE CAMBIOS IMPORTANTES**

```bash
#!/bin/bash
# Script: backup_pre_deployment.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/jtorreci/backups/pre_deployment"
PROJECT_DIR="/home/jtorreci/agenda/agenda-django"

mkdir -p $BACKUP_DIR

# Backup completo de BD
sudo -u postgres pg_dump -h localhost -p 5432 -U postgres agenda_db > $BACKUP_DIR/agenda_db_pre_deploy_$DATE.sql

# Backup del código actual
cd $PROJECT_DIR
git rev-parse HEAD > $BACKUP_DIR/current_commit_$DATE.txt
tar -czf $BACKUP_DIR/agenda_complete_$DATE.tar.gz .

echo "Backup pre-deployment creado: $DATE"
echo "Commit actual: $(git rev-parse HEAD)"
echo "Archivos en: $BACKUP_DIR"
```

---

## ✅ **CHECKLIST DE VERIFICACIÓN POST-DESPLIEGUE**

### **Verificaciones Técnicas:**
- [ ] Servicios activos (gunicorn, nginx)
- [ ] Base de datos responde
- [ ] Migraciones aplicadas correctamente
- [ ] Archivos estáticos serving correctamente
- [ ] Logs sin errores críticos

### **Verificaciones Funcionales:**
- [ ] Login funciona
- [ ] Dashboard carga correctamente
- [ ] Crear actividad individual funciona
- [ ] Crear actividad multi-grupo funciona
- [ ] Editar actividades funciona
- [ ] Copiar actividades funciona
- [ ] Checkboxes de sincronización funcionan
- [ ] Dashboard muestra actividades multi-grupo como fila única

### **Comandos de Verificación:**

```bash
# 1. Verificar conectividad de BD
python manage.py dbshell -c "SELECT COUNT(*) FROM schedule_actividad;"

# 2. Verificar modelo ActividadGrupo
python manage.py shell -c "from schedule.models import ActividadGrupo; print(ActividadGrupo.objects.count())"

# 3. Verificar que el sitio responde
curl -I http://tu-dominio.com/

# 4. Verificar archivos estáticos
curl -I http://tu-dominio.com/static/css/bootstrap.min.css
```

---

## 🔧 **PASOS ESPECÍFICOS PARA TU SERVIDOR**

Basado en la información anterior sobre tu servidor:

```bash
# Conectar al servidor
ssh jtorreci@tu-servidor

# Ir al directorio del proyecto
cd /home/jtorreci/agenda/agenda-django

# Ejecutar todos los pasos mencionados arriba
# Prestar especial atención a:
# - La ruta del proyecto: /home/jtorreci/agenda/agenda-django
# - Los permisos de archivos estáticos
# - Los logs de Gunicorn y Nginx

# Verificar configuración de Nginx para archivos estáticos
sudo nginx -t
```

---

## 🎯 **RESUMEN EJECUTIVO**

### **Cambios Principales:**
1. ✅ **Nuevo modelo `ActividadGrupo`** - Permite actividades multi-grupo
2. ✅ **Sistema unificado de formularios** - Interfaz mejorada para crear/editar actividades
3. ✅ **Dashboard optimizado** - Actividades multi-grupo se muestran como fila única
4. ✅ **Funcionalidad de copia mejorada** - Copia completa de grupos y sincronización

### **Migración Crítica:**
- Se creará la tabla `schedule_actividadgrupo`
- Se mantiene compatibilidad con actividades existentes
- **No hay pérdida de datos** - los campos actuales se mantienen

### **Riesgos Identificados:**
- **MEDIO**: Conflicto de migraciones (ya resuelto localmente)
- **BAJO**: Constraint de nombres únicos de grupos
- **BAJO**: Archivos estáticos necesitan recarga

### **Tiempo Estimado de Despliegue:**
- Backup: 2-3 minutos
- Actualización código: 1-2 minutos  
- Migraciones: 1-2 minutos
- Verificación: 2-3 minutos
- **Total: 6-10 minutos de downtime**

### **Recomendación:**
✅ **Los cambios están listos para producción**. El sistema mantiene compatibilidad total con datos existentes y añade funcionalidad nueva sin romper features anteriores.

---

## 📝 **NOTAS IMPORTANTES**

1. **Antes del despliegue**: Asegúrate de hacer commit y push de todos los cambios locales
2. **Durante el despliegue**: Mantén abiertas las terminales de logs para monitorear errores
3. **Después del despliegue**: Prueba todas las funcionalidades clave antes de dar por terminado
4. **En caso de problemas**: Usa el rollback rápido y investiga en local antes de volver a desplegar

---

**Fecha de creación:** 16 de septiembre de 2025  
**Versión:** 1.0  
**Autor:** Claude Code Assistant