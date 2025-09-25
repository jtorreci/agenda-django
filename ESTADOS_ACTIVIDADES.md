# 📋 Sistema de Estados de Actividades

## 📊 **Resumen**

Este documento describe la implementación del **sistema de estados para actividades** que permite gestionar el ciclo de vida completo de las actividades académicas con tres estados: **Visible**, **Borrada** y **Archivada**.

## 🎯 **Estados definidos**

| Estado | Valor `estado` | Campo `activa` | Visible para | Acciones disponibles |
|--------|----------------|----------------|--------------|---------------------|
| **Visible** | `'visible'` | `True` | Profesor, Coordinador, Estudiante* | Editar, Borrar |
| **Borrada** | `'borrada'` | `False` | Solo Coordinador (tabla separada) | Restaurar, Archivar |
| **Archivada** | `'archivada'` | `False` | Solo Admin | Restaurar a Borrada |

*Los estudiantes solo ven actividades visibles que además estén aprobadas (`aprobada=True`)

## 🏗️ **Arquitectura técnica**

### **Modelo Actividad (schedule/models.py)**

```python
class Actividad(models.Model):
    # Estados
    ESTADO_VISIBLE = 'visible'
    ESTADO_BORRADA = 'borrada'
    ESTADO_ARCHIVADA = 'archivada'

    ESTADO_CHOICES = [
        (ESTADO_VISIBLE, 'Visible'),
        (ESTADO_BORRADA, 'Borrada'),
        (ESTADO_ARCHIVADA, 'Archivada'),
    ]

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_VISIBLE,
        help_text="Estado actual de la actividad"
    )

    # Campos legacy (compatibilidad)
    activa = models.BooleanField(default=True, help_text="LEGACY: Usar campo 'estado' en su lugar")
    aprobada = models.BooleanField(default=False)  # Mantiene lógica independiente
```

### **QuerySet y Manager personalizados**

```python
class ActividadQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(estado='visible')

    def borradas(self):
        return self.filter(estado='borrada')

    def archivadas(self):
        return self.filter(estado='archivada')

class ActividadManager(models.Manager):
    def get_queryset(self):
        return ActividadQuerySet(self.model, using=self._db)

    def visible(self):
        return self.get_queryset().visible()

    def borradas(self):
        return self.get_queryset().borradas()

    def archivadas(self):
        return self.get_queryset().archivadas()
```

### **Métodos del modelo**

```python
def borrar(self, usuario=None):
    """Borra la actividad (profesor) - coordinador puede restaurar"""

def restaurar(self, usuario=None):
    """Restaura la actividad desde borrada a visible"""

def archivar(self, usuario=None):
    """Archiva la actividad (coordinador) - solo admin puede restaurar"""

def restaurar_desde_archivo(self, usuario=None):
    """Restaura la actividad desde archivada a borrada (solo admin)"""
```

## 🔄 **Flujo de trabajo**

```
[VISIBLE] ──(Profesor borra)──> [BORRADA] ──(Coordinador archiva)──> [ARCHIVADA]
    ↑                              ↑                                      │
    └──(Coordinador restaura)──────┘                                      │
    ↑                                                                     │
    └──────────────(Admin restaura desde archivo)────────────────────────┘
```

## 📁 **Archivos modificados**

### **1. Modelo y lógica (schedule/models.py)**
- ✅ **Campo estado**: CharField con choices
- ✅ **QuerySet personalizado**: Filtros por estado
- ✅ **Manager personalizado**: Métodos `.visible()`, `.borradas()`, `.archivadas()`
- ✅ **Métodos de transición**: `.borrar()`, `.restaurar()`, `.archivar()`
- ✅ **Sincronización automática**: Campo `activa` se actualiza automáticamente
- ✅ **Logging**: Todas las transiciones se registran en `LogActividad`

### **2. Vista coordinador (users/views.py)**
- ✅ **Dashboard actualizado**: Usa `filter(estado='visible')` y `filter(estado='borrada')`
- ✅ **Vista AJAX nueva**: `archivar_actividad_ajax` con verificación de permisos
- ✅ **Permisos granulares**: Solo coordinadores de la titulación pueden archivar

### **3. Template coordinador (users/templates/users/coordinator_dashboard.html)**
- ✅ **Botón archivar**: En tabla de actividades borradas
- ✅ **JavaScript completo**: Función `archivarActividad()` con confirmación
- ✅ **AJAX integration**: Petición POST con CSRF token
- ✅ **UX mejorada**: Confirmación + recarga automática tras archivar

### **4. URLs (users/urls.py)**
- ✅ **Endpoint AJAX**: `ajax/actividad/archivar/`

## 🗄️ **Migración de datos**

### **Script: `migrate_estados_actividad.py`**

```bash
# Simular migración
python manage.py migrate_estados_actividad --dry-run

# Aplicar migración
python manage.py migrate_estados_actividad

# Reset todas a visible (para testing)
python manage.py migrate_estados_actividad --reset
```

**Lógica de migración:**
- `activa=True` → `estado='visible'`
- `activa=False` → `estado='borrada'`
- Verificación de consistencia post-migración

## 🔐 **Permisos y seguridad**

### **Vista AJAX archivar:**
- ✅ **Login requerido**: `@login_required`
- ✅ **Rol coordinador**: `@user_passes_test(is_coordinator)`
- ✅ **Solo POST**: `@require_http_methods(["POST"])`
- ✅ **Validación estado**: Solo se pueden archivar actividades borradas
- ✅ **Permisos titulación**: Solo coordinadores de la titulación respectiva

### **Verificaciones implementadas:**
```python
# Verificar que esté borrada
if not actividad.es_borrada():
    return JsonResponse({'error': 'Solo se pueden archivar actividades que estén borradas'})

# Verificar permisos de titulación
if request.user.role != 'ADMIN':
    user_coordinated_titulaciones = Titulacion.objects.filter(coordinador=request.user)
    activity_titulaciones = Titulacion.objects.filter(asignatura__actividad=actividad)

    if not activity_titulaciones.intersection(user_coordinated_titulaciones).exists():
        return JsonResponse({'error': 'No tienes permisos para archivar esta actividad'})
```

## 🧪 **Testing y validación**

### **Comandos de verificación:**
```bash
# Verificar configuración Django
python manage.py check

# Probar managers
python manage.py shell -c "from schedule.models import Actividad; print('Visible:', Actividad.objects.visible().count())"

# Verificar migración
python manage.py migrate_estados_actividad --dry-run
```

### **Casos de prueba:**
- ✅ **Estados correctos**: 3 visible, 1 borrada, 0 archivadas (tras migración)
- ✅ **Managers funcionando**: Filtros por estado operativos
- ✅ **Sincronización**: Campo `activa` se actualiza automáticamente
- ✅ **Sin errores**: Django check pasa sin problemas

## 🎨 **Interfaz usuario**

### **Dashboard coordinador:**
- **Tabla actividades**: Solo visibles (editables)
- **Tabla borradas**: Con botones "Restaurar" y "Archivar"
- **Botón archivar**: Icono archivo + tooltip + confirmación JavaScript

### **JavaScript implementado:**
```javascript
function archivarActividad(actividadId, actividadNombre) {
    if (!confirm(`¿Está seguro de que desea archivar la actividad "${actividadNombre}"?\n\nUna vez archivada, solo los administradores podrán restaurarla.`)) {
        return;
    }

    fetch('/users/ajax/actividad/archivar/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({'actividad_id': actividadId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert('Error: ' + data.error);
        }
    });
}
```

## 🔄 **Compatibilidad hacia atrás**

### **Campo legacy mantenido:**
- ✅ **Campo `activa`**: Se mantiene por compatibilidad
- ✅ **Sincronización automática**: Se actualiza en el `save()` del modelo
- ✅ **Lógica legacy**: Código existente sigue funcionando

### **Sincronización automática:**
```python
def save(self, *args, **kwargs):
    # Aplicar lógica de aprobación automática
    if not self.pk or not hasattr(self, '_approval_manually_set'):
        self.aprobada = self._get_default_approval_status()

    # Sincronizar campo legacy 'activa' con nuevo campo 'estado'
    self.activa = (self.estado == self.ESTADO_VISIBLE)

    super().save(*args, **kwargs)
```

## 📊 **Estadísticas post-implementación**

### **Migración aplicada:**
- **Total actividades**: 4
- **Migradas a visible**: 3 (eran `activa=True`)
- **Migradas a borrada**: 1 (era `activa=False`)
- **Archivadas**: 0 (nuevo estado disponible)

### **Funcionalidad disponible:**
- ✅ **Coordinadores**: Pueden archivar actividades borradas
- ✅ **Profesores**: Ven actividades visibles + tabla borradas (solo lectura)
- ✅ **Estudiantes**: Ven solo actividades visibles y aprobadas
- ✅ **Admins**: Acceso completo a todos los estados

## 🚀 **Próximos pasos sugeridos**

1. **Dashboard admin**: Añadir gestión de actividades archivadas
2. **Bulk operations**: Archivar múltiples actividades a la vez
3. **Audit trail**: Mejorar logging con más detalles
4. **Filtros avanzados**: Filtrar por estado en dashboards
5. **Notificaciones**: Avisar cuando se archiva una actividad

## 📝 **Notas técnicas**

- **Base de datos**: No requiere cambios adicionales en estructura
- **Performance**: Managers optimizados con QuerySets eficientes
- **Escalabilidad**: Fácil añadir nuevos estados en el futuro
- **Mantenimiento**: Código limpio y bien documentado

---

**Fecha implementación**: 2025-09-25
**Estado**: ✅ IMPLEMENTADO Y FUNCIONAL
**Próxima revisión**: Tras testing en producción