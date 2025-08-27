#Universidad #Calidad #Dirección 

[[Agenda del estudiante. Propuesta inicial]]


---

# 🚀 Plan de Desarrollo MVP: Agenda Académica Inteligente

**Objetivo:** Desarrollar un Producto Mínimo Viable (MVP) funcional, seguro y que aporte valor real en el menor tiempo posible.

**Estimación Total Orientativa:** 4 Semanas

---

## Fase 0: La Cimentación фундамент

_Duración estimada: 1 - 2 Días_

El objetivo es tener la estructura del proyecto lista y los modelos de datos definidos. Es el trabajo menos visible pero el más importante para la estabilidad a largo plazo.

- [ ] **Configuración del Entorno:**
    
    - [ ] Crear el proyecto Django y las apps (`users`, `academics`, `schedule`).
        
    - [ ] Inicializar el repositorio de **Git**.
        
    - [ ] Configurar `requirements.txt`.
        
- [ ] **Definición de Modelos:**
    
    - [ ] Escribir el código para todos los modelos: `CustomUser`, `Titulacion`, `Asignatura`, `TipoActividad`, `Actividad`, `VistaCalendario`.
        
    - [ ] Configurar `AUTH_USER_MODEL` en `settings.py`.
        
- [ ] **Base de Datos y Panel de Admin:**
    
    - [ ] Ejecutar `makemigrations` y `migrate`.
        
    - [ ] Registrar **todos** los modelos en sus respectivos `admin.py`.
        
    - [ ] Crear un superusuario y verificar que se pueden crear objetos de cada modelo desde el panel de admin.
        

---

## Fase 1: El Circuito Central (Profesor ➔ Estudiante) ❤️‍🔥

_Duración estimada: 1 Semana_

El objetivo es que un usuario pueda crear información y otro pueda consumirla. Al final de esta fase, la aplicación ya será útil.

- [ ] **Autenticación de Usuarios:**
    
    - [ ] Crear vistas y plantillas para el Registro de Usuario.
        
    - [ ] Crear vistas y plantillas para el Inicio de Sesión (Login).
        
    - [ ] Implementar el Cierre de Sesión (Logout).
        
- [ ] **CRUD de Actividades para el Profesor:**
    
    - [ ] Crear una vista protegida para que un profesor vea sus asignaturas.
        
    - [ ] Implementar el formulario para **Crear** y **Actualizar** actividades.
        
    - [ ] Implementar la lógica para **Eliminar** actividades.
        
    - [ ] Crear la vista para **Listar** las actividades creadas por el profesor.
        
- [ ] **Vista de Agenda para el Estudiante:**
    
    - [ ] Crear una vista protegida para el estudiante.
        
    - [ ] Implementar el formulario para que pueda seleccionar/actualizar sus asignaturas.
        
    - [ ] Mostrar una lista simple de actividades de las asignaturas seleccionadas, ordenadas por fecha.
        

---

## Fase 2: La Funcionalidad Estrella (Suscripción iCal) ✨

_Duración estimada: 3 - 4 Días_

Implementamos la característica que diferencia a esta aplicación y resuelve el problema principal del usuario: la sincronización de calendarios.

- [ ] **Panel de Vistas de Calendario:**
    
    - [ ] Diseñar la interfaz del panel.
        
    - [ ] Implementar el formulario para **Crear** una nueva vista (darle nombre y filtrar por asignaturas/tipo).
        
    - [ ] Implementar la lógica para **Eliminar** una vista.
        
    - [ ] Mostrar la lista de vistas creadas, cada una con su URL de suscripción para copiar.
        
- [ ] **Generador iCal Dinámico:**
    
    - [ ] Crear la vista que recibe el token de la URL.
        
    - [ ] Implementar la lógica para buscar los filtros y consultar las actividades correspondientes en la BBDD.
        
    - [ ] Generar la respuesta con el `Content-Type` correcto para iCal.
        
    - [ ] Probar la suscripción desde Google Calendar y/o Apple Calendar.
        

---

## Fase 3: Capas de Control y Calidad 🛠️

_Duración estimada: 1 Semana_

Añadimos las funcionalidades de gestión para roles superiores y las reglas de negocio clave.

- [ ] **Vistas de Coordinador:**
    
    - [ ] Crear la vista de supervisión para ver actividades de una titulación/semestre.
        
    - [ ] Implementar la lógica para eliminar actividades mal asignadas.
        
- [ ] **Gestión para Administradores:**
    
    - [ ] Crear el CRUD para `TipoActividad`.
        
    - [ ] Implementar la lógica para definir la `Fecha de Cierre` de la agenda inicial.
        
- [ ] **Integración de Correo Electrónico:**
    
    - [ ] Configurar el backend de email (ej. SendGrid, Mailgun).
        
    - [ ] Implementar el email de confirmación de registro.
        
    - [ ] Implementar la funcionalidad de envío de notificaciones del coordinador (opcional para el MVP, pero deseable).
        
- [ ] **Módulo de Reportes (HTML):**
    
    - [ ] Crear la vista protegida para el informe de KPIs.
        
    - [ ] Implementar las consultas (`queries`) para obtener las métricas.
        
    - [ ] Presentar los datos en una plantilla HTML simple.
        

---

## Consejos Transversales (A aplicar durante todo el proceso)

- [ ] **Usar el Admin de Django:** Para toda la gestión de datos que no requiera una interfaz personalizada en el MVP (ej. asignar profesores a asignaturas).
    
- [ ] **Escribir Pruebas (Tests):** Crear tests unitarios al menos para la lógica de negocio más crítica (permisos de roles, generación de iCal).
    
- [ ] **Frontend Simple:** No invertir tiempo en CSS complejo o JavaScript avanzado. La funcionalidad es la prioridad.
    
- [ ] **Commits Frecuentes en Git:** Hacer `commit` al finalizar cada tarea pequeña con un mensaje claro. Ejemplo: `git commit -m "feat: Implement user registration view"`.