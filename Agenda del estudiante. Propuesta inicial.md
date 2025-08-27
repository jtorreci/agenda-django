#Universidad #Calidad #Dirección 

# 📝 Proyecto: Agenda Académica Inteligente (Django)

## 1. Descripción de la Aplicación

**Agenda Académica Inteligente** es una aplicación web integral desarrollada en Django, diseñada para centralizar, personalizar y auditar la planificación académica. Su objetivo es facilitar la coordinación entre profesores, coordinadores y estudiantes, y a la vez, generar evidencias medibles para los sistemas de gestión de calidad de la institución.

Las funcionalidades clave incluyen:

- Un sistema de **"agenda inicial"** con fecha de cierre para estabilizar la planificación semestral.
    
- Un **panel de creación de vistas** que permite a los usuarios generar URLs de suscripción a calendarios iCal dinámicos y totalmente personalizados.
    
- Un **módulo de reportes de KPIs** para administradores, que permite generar informes en HTML y PDF con las métricas clave de uso y contenido de la plataforma, sirviendo como evidencia para auditorías de calidad.
    

## 2. Arquitectura y Modelos Clave

- **Backend:** **Django Framework**.
    
- **Base de Datos:** **PostgreSQL**.
    
- **Frontend:** **Plantillas de Django con HTML, CSS y JavaScript/HTMX**.
    
- **Librerías Clave:**
    
    - `django-ical` o `icalendar` (para generar iCal).
        
    - `WeasyPrint` o `ReportLab` (para generar PDF desde HTML).
        
- **Modelos de Datos Principales:**
    
    - `CustomUser`: Usuarios y roles.
        
    - `Titulacion`, `Asignatura`: Estructura académica.
        
    - **`TipoActividad` (Nuevo):** Un modelo gestionado por el administrador para categorizar las actividades (Ej: Examen Parcial, Práctica de Laboratorio, Conferencia).
        
    - `Actividad`: Tareas y eventos, ahora con una `ForeignKey` obligatoria a `TipoActividad`.
        
    - `VistaCalendario`: Los filtros de calendario personalizados que crea cada usuario.
        

## 3. Árbol de Archivos Inicial

```
agenda_academica/
├── ...
├── apps/
│   ├── users/
│   ├── academics/
│   │   └── models.py # Titulacion, Asignatura, TipoActividad
│   ├── schedule/
│   │   └── models.py # Actividad, VistaCalendario
│   └── reports/      # NUEVA APP para la lógica de KPIs y generación de informes
│       ├── __init__.py
│       ├── views.py
│       └── urls.py
└── ...
```

---

## 4. Panel de Vistas de Calendario (Funcionalidad Transversal)

Esta funcionalidad se mantiene como se describió, pero ahora se enriquece. Al crear o editar una vista, el usuario podrá **filtrar también por tipo de actividad**, permitiendo crear calendarios aún más específicos (ej: "Solo Exámenes de todas mis asignaturas").

- **Crear (C), Listar (R), Actualizar (U) y Eliminar (D)** Vistas personalizadas.
    
- **Filtros disponibles:** Asignaturas, **Tipos de Actividad**.
    
- Cada vista genera una **URL de suscripción iCal** única.
    

## 5. Sistema de Reportes y KPIs (Exclusivo para Administradores)

Se creará una nueva sección en el panel de administración para la inteligencia de negocio y la calidad.

- **Interfaz de Reportes:** Una vista HTML donde el administrador puede seleccionar el curso académico o un rango de fechas para generar un informe.
    
- **KPIs a Medir:** El informe incluirá, como mínimo:
    
    - **Configuración:** Fecha de Cierre de la Agenda Inicial para el periodo.
        
    - **Contenido Académico:** Nº de Titulaciones, Nº de Asignaturas registradas.
        
    - **Volumen de Actividades:** Nº total de actividades creadas, y un gráfico con el desglose por `TipoActividad`.
        
    - **Métricas de Uso:** Nº de usuarios por rol, Nº total de Vistas de Calendario generadas por los usuarios.
        
- **Formatos de Salida:**
    
    1. **Visualización en HTML** con gráficos y enlaces.
        
    2. Botón **"Exportar a PDF"** para generar un documento formal y archivable.
        

## 6. Funcionalidades Detalladas por Rol

### 👨‍🎓 **Estudiante**

- Selección de sus asignaturas.
    
- Acceso al **Panel de Vistas** para crear sus calendarios personalizados.
    

### 👨‍🏫 **Profesor** (Hereda funciones de Estudiante)

- Gestión de Actividades (CRUD). Al crear una actividad, deberá **seleccionar obligatoriamente su tipo** de una lista predefinida.
    
- Acceso al **Panel de Vistas** para sus propias asignaturas.
    

### 🧑‍💼 **Coordinador** (Hereda funciones de Profesor y Estudiante)

- Supervisión de agendas y detección de sobrecarga.
    
- Acceso al **Panel de Vistas** con filtros ampliados por titulación y semestre.
    

### 👷 **Administrador** (Hereda todas las funciones)

- Dashboard de control y gestión de usuarios, roles y asignaturas.
    
- **Gestión de Tipos de Actividad (CRUD):** Crear, editar y eliminar las categorías que los profesores usarán.
    
- **Gestión de Fecha de Cierre** para la "agenda inicial".
    
- **Generación de Reportes de KPIs** con exportación a PDF/HTML.
    

---

## 7. Prompt para Pair Programming con Gemini CLI

Este es el prompt definitivo que encapsula la visión completa del proyecto.

```
Hola Gemini. Vamos a empezar un proyecto de desarrollo de software juntos en modo pair programming.

**Mi rol:** Soy el arquitecto del producto. Te proporcionaré los requisitos, la lógica de negocio y tomaré las decisiones de diseño.

**Tu rol:** Eres mi programador experto en Django. Tu trabajo es escribir código limpio, eficiente y seguro, seguir las mejores prácticas de Django, explicarme las decisiones técnicas que tomas y sugerir mejoras.

**El Proyecto:**
Vamos a construir una aplicación web integral llamada "Agenda Académica Inteligente". Será una herramienta de planificación para estudiantes y profesores, y a la vez, un sistema de generación de evidencias de calidad para la administración. Te adjunto el documento de diseño final y completo.

[Pega aquí todo el contenido Markdown anterior, desde el título "📝 Proyecto: Agenda Académica Inteligente (Django)" hasta el final de la sección de funcionalidades]

**Nuestra Primera Tarea:**
Nuestra base de modelos es ahora más completa y fundamental para el éxito. Necesitamos definir toda la estructura de datos desde el principio.

Por favor, guíame a través de los siguientes pasos:
1.  Crear las aplicaciones Django `users`, `academics` y `schedule`. (Dejaremos la app `reports` para más adelante).
2.  En `users`, definir el modelo `CustomUser` con su campo `role`.
3.  En `academics`, definir tres modelos: `Titulacion`, `Asignatura` y `TipoActividad`.
4.  En `schedule`, definir dos modelos:
    * `Actividad`: con `ForeignKey` a `Asignatura` y a `TipoActividad`.
    * `VistaCalendario`: con `ForeignKey` a `CustomUser` y `ManyToManyField` a `Asignatura` y `TipoActividad`, además de su `token` UUID.
5.  Configurar el `AUTH_USER_MODEL` en `settings.py`.
6.  Muéstrame el código completo para los tres archivos `models.py` y los cambios necesarios en `settings.py`.

Empecemos por el punto 1, la creación de las apps. Una vez tengamos los modelos, definiremos los datos iniciales para `TipoActividad`.
```

## 8. Plan de trabajo
[[Agenda del estudiante. Plan de trabajo]]
