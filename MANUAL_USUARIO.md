# Manual de Usuario - Sistema de Agenda Académica

## Usuarios de prueba

Las credenciales de prueba ya no se publican aquí. Crea las cuentas que necesites con `python manage.py createsuperuser` o desde el panel de administración de Django, y usa contraseñas propias.

## 🔐 Acceso al Sistema

1. Navega a `http://127.0.0.1:8000/`
2. Haz clic en "Login" o ve directamente a `http://127.0.0.1:8000/login/`
3. Introduce tu usuario y contraseña
4. Serás redirigido al dashboard correspondiente a tu rol

---

# 👨‍💼 MANUAL DE ADMINISTRADOR

## Funcionalidades Principales

### 1. **Acceso al Sistema**
- Inicia sesión con credenciales de administrador
- Accede a múltiples dashboards: Admin, Coordinator, Teacher

### 2. **Gestión de Coordinadores**
- **Ubicación:** Dashboard de Admin → "Assign Coordinators"
- **Función:** Asignar coordinadores a titulaciones específicas
- **Proceso:**
  1. Selecciona un usuario del dropdown para cada titulación
  2. Haz clic en "Guardar Asignaciones" 
  3. Confirma los cambios
- **Reglas:** 
  - Solo admins pueden asignar coordinadores
  - Los usuarios asignados automáticamente reciben el rol COORDINATOR
  - Los usuarios que dejan de ser coordinadores se degradan a TEACHER

### 3. **Gestión de Tipos de Actividad**
- **Ubicación:** Dashboard de Admin → "Manage Activity Types"
- **Funciones:**
  - Crear nuevos tipos de actividad
  - Editar tipos existentes
  - Eliminar tipos no utilizados

### 4. **Configuración de la Agenda**
- **Ubicación:** Dashboard de Admin → "Agenda Settings"
- **Función:** Establecer fecha de cierre de la agenda
- **Uso:** Define hasta cuándo se pueden crear/modificar actividades

### 5. **Reportes KPI**
- **Ubicación:** Dashboard de Admin → KPI Report
- **Información disponible:**
  - Total de usuarios por rol
  - Total de actividades
  - Total de titulaciones

### 6. **Panel de Django Admin**
- **Acceso:** `http://127.0.0.1:8000/admin/`
- **Funciones avanzadas:**
  - Gestión completa de usuarios
  - Gestión de modelos de datos
  - Configuraciones del sistema

---

# 👨‍🎓 MANUAL DE COORDINADOR

## Funcionalidades Principales

### 1. **Dashboard Principal**
- **Vista:** Lista de actividades y calendario
- **Filtros disponibles:**
  - Por titulación (solo las que coordina)
  - Por asignatura, curso, semestre
  - Por tipo de actividad
  - Por estado de evaluación
  - Por estado de aprobación

### 2. **Aprobación de Actividades**
- **Reglas automáticas:**
  - ✅ **No evaluables:** Aprobadas automáticamente
  - ✅ **Evaluables < 10%:** Aprobadas automáticamente  
  - ❌ **Evaluables ≥ 10%:** Requieren aprobación manual

### 3. **Control de Aprobaciones**
- **Método:** Checkboxes en la tabla de actividades
- **Restricción:** Solo actividades de titulaciones que coordina
- **Efecto:** Cambios se aplican inmediatamente

### 4. **Gestión de Actividades**
- **Crear:** Botón "Create Activity"
- **Editar:** Botón "Edit" en cada actividad
- **Eliminar:** Botón "Delete" en cada actividad (soft delete)

### 5. **Notificaciones**
- **Función:** Enviar notificaciones a todos los usuarios
- **Uso:** Para comunicados importantes sobre actividades

### 6. **Vista de Calendario**
- **Funciones:**
  - Vista mensual, semanal, lista
  - Filtrado dinámico según selecciones
  - Eventos en tiempo real

---

# 👨‍🏫 MANUAL DE PROFESOR

## Funcionalidades Principales

### 1. **Selección de Asignaturas**
- **Ubicación:** Dashboard → "Manage Selection"
- **Proceso:**
  1. Selecciona una titulación
  2. Marca las asignaturas que impartes
  3. Guarda la selección

### 2. **Gestión de Actividades**

#### **Crear Actividad:**
1. Botón "Create Activity"
2. Completa el formulario:
   - Nombre de la actividad
   - Tipo de actividad
   - Asignaturas (solo las tuyas)
   - Fechas de inicio y fin
   - Descripción (opcional)
   - Configuración de evaluación

#### **Configuración de Evaluación:**
- **No evaluable:** Se aprueba automáticamente
- **Evaluable < 10%:** Se aprueba automáticamente
- **Evaluable ≥ 10%:** Requiere aprobación del coordinador

#### **Editar/Eliminar:**
- Usa los botones correspondientes en la tabla
- Las eliminaciones son "soft delete" (se marcan como inactivas)

### 3. **Dashboard con Filtros**
- **Sidebar:** Checkboxes para filtrar por asignaturas
- **Botón "Select All":** Alterna todas las selecciones
- **Filtrado dinámico:** Actualiza lista y calendario automáticamente

### 4. **Vista de Calendario**
- **FullCalendar integrado**
- **Vistas:** Mes, semana, lista
- **Filtrado:** Según asignaturas seleccionadas

### 5. **Feeds iCal**

#### **Crear Feed iCal:**
1. Accordion "iCal Feed Configurations"
2. "Create New iCal Feed"
3. Configura:
   - Nombre del feed
   - Asignaturas incluidas
   - Tipos de actividad

#### **Gestionar Feeds:**
- **Copy Link:** Copia URL para calendarios externos
- **Delete:** Elimina el feed
- **URL típica:** `http://127.0.0.1:8000/ical/[token]/`

### 6. **Vista como Estudiante**
- **Botón:** "View as Student"
- **Función:** Ver el sistema desde la perspectiva de un estudiante

---

# 👨‍🎓 MANUAL DE ESTUDIANTE

## Funcionalidades Principales

### 1. **Selección de Asignaturas**
- **Ubicación:** Dashboard → "Select/Update Subjects"
- **Proceso:**
  1. Selecciona una titulación
  2. Marca las asignaturas en las que estás matriculado
  3. Guarda la selección

### 2. **Dashboard Principal**

#### **Sidebar Izquierdo:**
- **Lista de asignaturas matriculadas:** Con checkboxes para filtrar
- **Botón "Select All/Deselect All":** Control rápido de filtros
- **Accordion iCal Feeds:** Gestión de calendarios personalizados

#### **Área Principal:**
- **Pestaña "Activity List":** Tabla con actividades filtradas
- **Pestaña "Calendar View":** Calendario FullCalendar interactivo

### 3. **Filtrado de Actividades**
- **Método:** Checkboxes en el sidebar
- **Efecto:** Filtra tanto la lista como el calendario
- **Persistencia:** Los filtros se mantienen al cambiar de pestaña

### 4. **Vista de Actividades**
- **Solo actividades aprobadas:** Por razones de fiabilidad académica
- **Información mostrada:**
  - Nombre de la actividad
  - Asignatura(s) asociada(s)
  - Tipo de actividad
  - Fechas de inicio y fin

### 5. **Calendario Personal**
- **FullCalendar:** Vista mensual, semanal, lista
- **Eventos dinámicos:** Se actualizan según filtros de asignaturas
- **Información:** Muestra solo actividades aprobadas y activas

### 6. **Feeds iCal Personalizados**

#### **Crear Feed:**
1. Accordion "iCal Feed Configurations" → "Create New iCal Feed"
2. Configurar:
   - Nombre del feed
   - Asignaturas específicas
   - Tipos de actividad deseados

#### **Usar Feed:**
- **Copy Link:** Obtén URL para tu calendario externo
- **Compatible con:** Google Calendar, Outlook, Apple Calendar, etc.
- **Actualización:** Automática según configuración del calendario externo

#### **Gestión:**
- **Ver feeds existentes:** Lista en el accordion
- **Eliminar:** Botón "Delete" en cada feed
- **Copiar enlace:** Botón "Copy Link" con feedback visual

---

## 🔄 Flujo de Trabajo Típico

### Para Profesores:
1. Seleccionar asignaturas que imparte
2. Crear actividades para sus asignaturas
3. Las actividades se aprueban automáticamente según reglas
4. Configurar feeds iCal para compartir calendario

### Para Coordinadores:
1. Revisar actividades de titulaciones asignadas
2. Aprobar/desaprobar actividades evaluables ≥10%
3. Gestionar tipos de actividad
4. Enviar notificaciones cuando sea necesario

### Para Estudiantes:
1. Seleccionar asignaturas en las que está matriculado
2. Filtrar actividades por asignaturas de interés
3. Consultar calendario personal
4. Configurar feeds iCal para sincronizar con calendario personal

### Para Administradores:
1. Asignar coordinadores a titulaciones
2. Gestionar tipos de actividad del sistema
3. Configurar parámetros globales
4. Monitorear KPIs del sistema

---

## 📱 Características Técnicas

### **Responsive Design:**
- Compatible con escritorio, tablet y móvil
- Sidebar colapsible en pantallas pequeñas

### **Tecnologías:**
- **Backend:** Django 5.2.5
- **Frontend:** Bootstrap 5, FullCalendar 5.11.3
- **Base de datos:** SQLite (desarrollo)

### **URLs Importantes:**
- **Inicio:** `http://127.0.0.1:8000/`
- **Login:** `http://127.0.0.1:8000/login/`
- **Admin Django:** `http://127.0.0.1:8000/admin/`
- **API Eventos Estudiante:** `http://127.0.0.1:8000/users/api/student_events/`
- **Feed iCal:** `http://127.0.0.1:8000/ical/[token]/`

---

## 🆘 Solución de Problemas

### **No veo actividades en mi dashboard:**
- Verifica que las actividades estén aprobadas (estudiantes)
- Comprueba que tengas asignaturas seleccionadas
- Asegúrate de que las actividades estén activas

### **No puedo aprobar actividades (coordinador):**
- Verifica que seas coordinador de esa titulación
- Solo se pueden aprobar actividades de tus titulaciones asignadas

### **El feed iCal no funciona:**
- Verifica que la URL sea correcta y completa
- Asegúrate de que el token no haya expirado
- Comprueba la configuración del feed (asignaturas y tipos incluidos)

### **Error de permisos:**
- Verifica que tengas el rol correcto para la acción
- Contacta al administrador si necesitas cambios de rol

---

**Versión del Manual:** 1.0  
**Última actualización:** Diciembre 2024  
**Desarrollado para:** Django 5.2.5