# Milestones de Desarrollo - Agenda Académica

## Estado: Recopilando Requisitos

Este documento registra las correcciones y nuevas funcionalidades identificadas para el desarrollo de la Agenda Académica.

---

## Milestone 1: Correcciones y Mejoras Base

### 1.1 Separación de actividades activas/borradas en dashboard de profesor
**Descripción:** Mejorar la claridad del dashboard de profesor separando las actividades activas de las borradas.

**Tareas:**
- [ ] Modificar la vista del dashboard de profesor para mostrar solo actividades activas por defecto
- [ ] Crear tabla separada para actividades borradas (soft-deleted)
- [ ] Implementar botón "Ver actividades borradas" que muestre/oculte la tabla de actividades inactivas
- [ ] Actualizar template del dashboard con la nueva estructura
- [ ] Añadir estilos CSS para diferenciar visualmente las actividades borradas

**Archivos afectados:**
- `users/views.py` (dashboard de profesor)
- `templates/users/teacher_dashboard.html`
- Posibles archivos CSS para estilos

### 1.2 Cambio de formato de hora en vistas de calendario
**Descripción:** Cambiar el formato de hora de 12 horas (AM/PM) a formato 24 horas en todas las vistas de calendario para mejor legibilidad.

**Tareas:**
- [ ] Identificar todos los templates que muestran horarios en vistas de calendario
- [ ] Cambiar filtros de Django de formato 12h a 24h (de `|date:"g:i A"` a `|date:"H:i"`)
- [ ] Revisar archivos JavaScript que manejen formato de fecha/hora
- [ ] Verificar que el cambio se aplique consistentemente en:
  - Vista de calendario principal
  - iCal feeds generados
  - Formularios de actividades
  - Dashboards con horarios

**Archivos afectados:**
- Templates de calendario en `schedule/templates/`
- Posibles archivos JavaScript para manejo de fechas
- Views que generan iCal feeds
- Templates de dashboards con información de horarios

### 1.3 Corrección de zona horaria en formularios de edición
**Descripción:** Solucionar el problema de desfase de 2 horas en los formularios de edición de actividades. Las horas se muestran incorrectamente (2 horas menos) y al guardar se almacenan con la hora incorrecta.

**Problema identificado:**
- Al editar una actividad, el formulario muestra las horas con 2 horas de diferencia respecto a las introducidas originalmente
- Al guardar, se almacena la hora incorrecta
- Posible problema de conversión entre UTC y zona horaria local (Europe/Madrid)

**Tareas:**
- [ ] Investigar el manejo de timezone en los formularios de actividad
- [ ] Revisar la configuración de `USE_TZ`, `TIME_ZONE` en settings.py
- [ ] Verificar widgets de datetime en los formularios
- [ ] Revisar conversiones de timezone en las vistas de edición
- [ ] Corregir la lógica de conversión para mostrar/guardar correctamente las horas
- [ ] Verificar que el problema no afecte a otras partes de la aplicación
- [ ] Probar thoroughly con diferentes escenarios de edición

**Archivos afectados:**
- `schedule/forms.py` (formularios de actividad)
- `schedule/views.py` (vistas de edición de actividad)
- `settings.py` (configuración de timezone)
- Templates con widgets de datetime
- Posible middleware de timezone

### 1.4 Mejora de visualización de horarios en actividades múltiples
**Descripción:** Corregir problemas de visualización en las casillas de días-horas en actividades múltiples donde las horas no se ven completamente y requieren desplazar el cursor para visualizarlas.

**Problema identificado:**
- En formularios/vistas de actividades múltiples las casillas de horarios son demasiado pequeñas
- El texto de la hora se corta y no es completamente visible
- Mala experiencia de usuario al tener que hacer hover o scroll para ver información básica

**Tareas:**
- [ ] Identificar los elementos CSS que controlan el ancho de las casillas de hora
- [ ] Revisar templates de actividades múltiples (`multi_group_activity_form.html`)
- [ ] Ajustar estilos CSS para hacer las casillas más anchas
- [ ] Verificar que el texto se muestre completamente sin necesidad de hover
- [ ] Probar en diferentes resoluciones de pantalla
- [ ] Asegurar que no se rompa el diseño responsive
- [ ] Revisar también tablas de visualización de actividades múltiples en dashboards

**Archivos afectados:**
- `schedule/templates/schedule/multi_group_activity_form.html`
- Archivos CSS del proyecto
- Templates de dashboard que muestren actividades múltiples
- Posibles archivos JavaScript que manejen la visualización

## Milestone 2: Nuevas Funcionalidades

### 2.1 Botón "Ver Actividad" y generación de PDF convocatoria
**Descripción:** Añadir un botón "Ver Actividad" en el dashboard de profesor que permita visualizar toda la información de la actividad y generar un PDF que sirva como convocatoria oficial.

**Funcionalidad:**
- Botón adicional junto a Editar, Copiar, Borrar en la tabla de actividades del dashboard
- Modal o página dedicada que muestre todos los datos de la actividad de forma detallada
- Generación de PDF con formato de convocatoria oficial incluyendo:
  - Información completa de la actividad
  - Asignaturas asociadas
  - Fechas y horarios
  - Descripción y detalles
  - Información de evaluación (si aplica)
  - Formato profesional para uso oficial

**Tareas:**
- [ ] Crear vista para mostrar detalles completos de la actividad
- [ ] Diseñar template para visualización detallada de actividad
- [ ] Implementar generación de PDF con ReportLab (ya disponible en requirements)
- [ ] Crear template/layout para PDF de convocatoria
- [ ] Añadir botón "Ver" en dashboard de profesor
- [ ] Crear modal o página dedicada para mostrar información
- [ ] Implementar descarga de PDF desde la vista de detalles
- [ ] Añadir estilos CSS para la vista de detalles
- [ ] Configurar URL y routing para la nueva funcionalidad

**Archivos afectados:**
- `schedule/views.py` (nueva vista de detalles y generación PDF)
- `users/templates/users/teacher_dashboard.html` (añadir botón)
- Nuevo template para vista de detalles de actividad
- Nuevo módulo/función para generación de PDF
- `schedule/urls.py` (nueva ruta)
- Archivos CSS para estilos

## Milestone 3: Optimizaciones y Refinamientos
*Pendiente de definición*

---

**Última actualización:** 2025-01-25
**Estado:** Recopilando requisitos del usuario