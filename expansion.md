# 🚀 EXPANSIÓN: Sistema Integral de Gestión Académica

## 📋 **Resumen Ejecutivo**

Este documento define la transformación de la **Agenda Académica Django** actual en un **Sistema Integral de Gestión Académica** que actuará como contenedor de múltiples aplicaciones especializadas para la gestión completa de una escuela universitaria.

## 🎯 **Visión del Proyecto**

### **Estado Actual (v1.0)**
- ✅ **Aplicación funcional**: Agenda de actividades académicas
- ✅ **Sistema de roles**: Múltiples perfiles por usuario
- ✅ **Arquitectura sólida**: Django modular, PostgreSQL, i18n
- ✅ **UI consistente**: Bootstrap, responsive, PWA-ready

### **Estado Objetivo (v2.0)**
- 🎯 **Contenedor de aplicaciones**: Hub central de gestión académica
- 🎯 **4 módulos integrados**: Agenda + Asistencia + TFG + Planes Docentes
- 🎯 **Experiencia unificada**: Dashboard personalizado por rol
- 🎯 **Optimización móvil**: PWA con funcionalidades específicas por dispositivo

## 🏗️ **Decisiones de Diseño Críticas**

### **1. Arquitectura de Desarrollo**
- **Estrategia**: Copia completa del proyecto actual a carpeta nueva
- **Base de datos**: Migración de PostgreSQL de producción a local para pruebas reales
- **Preservación**: Aplicación original intacta y funcional en servidor
- **Entorno**: PostgreSQL local para mantener consistencia con producción

### **2. Sistema de Roles y Permisos**
**✅ CONFIRMADO**: El sistema actual ya soporta múltiples roles simultáneos por usuario
```python
# Arquitectura existente perfecta para casos complejos:
usuario.asignar_perfil('TEACHER')        # Profesor
usuario.asignar_perfil('COORDINATOR')    # + Coordinador
usuario.asignar_perfil('DIRECTION_TEAM') # + Equipo dirección
usuario.asignar_perfil('COMMISSION_TFG') # + Comisión TFG
```

**Modelos clave:**
- `CustomUser`: Usuario base con sistema dual (legacy + nuevo)
- `TipoPerfil`: Roles dinámicos configurables con permisos JSON
- `AsignacionPerfil`: Tabla intermedia con metadata de asignaciones

### **3. Estrategia de Navegación**
- **Desktop**: Menú lateral con acceso a todas las aplicaciones
- **Tablet**: Menú colapsible adaptativo
- **Móvil**: Por defecto → App de asistencia (fichar), menú hamburguesa
- **PWA**: Instalable, notificaciones push, funcionalidad offline básica

### **4. Integración de Datos**
- **Modelo central**: `CustomUser`, `Asignatura`, `Titulacion` (ya existentes)
- **Extensiones**: `Horario`, `Aula`, perfiles específicos por app
- **Relaciones cross-app**: TFG ↔ Estudiante ↔ Asignaturas ↔ Agenda

## 📱 **Aplicaciones del Sistema**

### **App 1: Agenda (Existente - schedule/)**
- ✅ **Funcional**: Gestión completa de actividades académicas
- 🔧 **Mejoras planificadas**: Integración con horarios de clase, notificaciones cross-app

### **App 2: Asistencia (Nueva - attendance/)**
- 🎯 **MVP**: Fichar entrada/salida profesores y estudiantes
- 🎯 **Avanzado**: Geolocalización, QR codes, reportes automáticos
- 🎯 **Integración**: Sincronización con horarios y agenda

### **App 3: Gestión TFG (Nueva - tfg/)**
- 🎯 **Workflow completo**: Propuesta → Asignación → Desarrollo → Defensa
- 🎯 **Roles**: Estudiantes, tutores, tribunales, coordinadores
- 🎯 **Features**: Timeline visual, documentos, calendarios de defensas

### **App 4: Planes Docentes (Nueva - teaching/)**
- 🎯 **Asistente inteligente**: Plantillas dinámicas, sugerencias automáticas
- 🎯 **Colaborativo**: Revisión por coordinadores, versionado
- 🎯 **Normativo**: Integración con BOE, validaciones automáticas

### **App 5: Core (Nueva - core/)**
- 🎯 **Base del sistema**: Layouts, menús dinámicos, página inicio
- 🎯 **Permisos**: Middleware de apps, decoradores personalizados
- 🎯 **Dashboard**: Widgets personalizados por rol, estadísticas globales

## 🗂️ **Estructura del Proyecto Expandido**

```
gestion_academica/  # Nuevo proyecto
├── core/          # App base: menús, layouts, dashboard
├── users/         # Gestión usuarios (migrado + expandido)
├── academics/     # Datos académicos (migrado + expandido)
├── schedule/      # Agenda actividades (migrado tal cual)
├── attendance/    # NUEVA: Control asistencia
├── tfg/          # NUEVA: Gestión TFG/TFE
├── teaching/     # NUEVA: Planes docentes
├── static/
│   ├── core/     # Estilos base, componentes comunes
│   ├── mobile/   # Estilos específicos móvil
│   └── js/       # JavaScript modular por app
└── templates/
    ├── core/     # Layouts base, componentes reutilizables
    ├── mobile/   # Templates móvil específicos
    └── includes/ # Componentes parciales
```

## 💾 **Configuración Base de Datos**

### **Setup PostgreSQL Local**
```bash
# Configuración inicial
createdb gestion_academica_dev
pg_restore -d gestion_academica_dev backup_produccion.dump

# Settings Django locales
DATABASE_URL=postgresql://user:pass@localhost/gestion_academica_dev
DEBUG=True
USE_POSTGRESQL=True
```

### **Migración de Datos**
- ✅ **Preservar datos existentes**: Importar dump completo de producción
- ✅ **Estructura actual**: Mantener compatibilidad total
- ✅ **Extensiones**: Nuevas tablas sin afectar existentes

## 🎨 **Design System**

### **Componentes UI**
- **Base**: Bootstrap 5 + iconos Bootstrap Icons
- **Tema**: Consistente con agenda actual
- **Responsive**: Mobile-first con adaptaciones específicas
- **Accesibilidad**: WCAG 2.1 AA compliance

### **Patrones de Navegación**
```
Desktop: [Logo] [Agenda] [Asistencia] [TFG] [Planes] [Perfil]
Tablet:  [☰] Logo [Notificaciones] [Perfil]
Móvil:   [☰] Logo [🔔] [Fichar] [👤]
```

## 🔐 **Nuevos Perfiles de Usuario**

### **Perfiles Base (existentes)**
- `STUDENT`: Estudiante
- `TEACHER`: Profesor
- `COORDINATOR`: Coordinador de titulación
- `ADMIN`: Administrador

### **Perfiles Expandidos (nuevos)**
- `DIRECTION_TEAM`: Equipo de dirección
- `SECRETARY`: Secretaría académica
- `COMMISSION_TFG`: Comisión de TFG/TFE
- `COMMISSION_ACADEMIC`: Comisión académica
- `COMMISSION_QUALITY`: Comisión de calidad
- `TRIBUNAL_MEMBER`: Miembro de tribunal
- `LIBRARY_STAFF`: Personal biblioteca
- `IT_SUPPORT`: Soporte técnico

### **Casos de Uso de Roles Múltiples**
```python
# Ejemplos reales del sistema:
profesor_coordinador = User.objects.get(email='coord@unex.es')
# Tiene: TEACHER + COORDINATOR + COMMISSION_ACADEMIC

director = User.objects.get(email='director@unex.es')
# Tiene: TEACHER + COORDINATOR + DIRECTION_TEAM + ADMIN

secretario = User.objects.get(email='secretario@unex.es')
# Tiene: SECRETARY + DIRECTION_TEAM + COMMISSION_TFG
```

## 📊 **Flujos de Trabajo Integrados**

### **Flujo Asistencia ↔ Agenda**
1. Profesor crea actividad en agenda
2. Sistema genera automáticamente horario en asistencia
3. Estudiantes/profesores fichan entrada/salida
4. Reportes de asistencia se vinculan a actividades específicas

### **Flujo TFG ↔ Estudiantes ↔ Agenda**
1. Estudiante propone TFG vinculado a sus asignaturas
2. Coordinador asigna tutor de esas asignaturas
3. Reuniones de seguimiento se crean automáticamente en agenda
4. Defensas se programan como actividades especiales

### **Flujo Planes ↔ Asignaturas ↔ Agenda**
1. Profesor redacta plan docente para asignatura
2. Actividades del plan se sugieren para agenda automáticamente
3. Coordinador revisa/aprueba plan y actividades vinculadas
4. Sistema valida coherencia entre plan y calendario real

## 🚀 **Hoja de Ruta de Desarrollo**

### **Fase 1: Base y Core (3 semanas)**
- Copia proyecto, configuración PostgreSQL local
- Creación app `core` con layouts base
- Sistema de menús dinámicos
- Dashboard adaptativo

### **Fase 2: Asistencia MVP (4 semanas)**
- Modelos básicos de horarios y asistencia
- Interface web para fichar
- PWA móvil optimizada
- Reportes básicos

### **Fase 3: TFG Básico (5 semanas)**
- Workflow propuesta → asignación → seguimiento
- Gestión documental
- Timeline de proceso
- Integración con usuarios existentes

### **Fase 4: Planes Docentes (4 semanas)**
- Editor de planes con plantillas
- Sistema de revisión colaborativo
- Validaciones automáticas
- Exportación/importación

### **Fase 5: Integración Final (3 semanas)**
- Cross-app notifications
- Dashboard unificado
- Optimizaciones de performance
- Testing integral

## 📝 **Notas de Implementación**

### **Para la Primera Sesión**
1. **Copiar proyecto completo** a nueva carpeta
2. **Configurar PostgreSQL local** con datos de producción
3. **Crear app core** con estructura base
4. **Implementar menú dinámico** básico
5. **Verificar compatibilidad** total con funcionalidad existente

### **Principios de Desarrollo**
- ✅ **Backward compatibility**: No romper funcionalidad existente
- ✅ **Incremental development**: Apps independientes que se integran
- ✅ **Data preservation**: Datos actuales siempre accesibles
- ✅ **Performance first**: Optimización desde diseño
- ✅ **Mobile responsive**: PWA como ciudadano de primera clase

### **Consideraciones Técnicas**
- **Cache strategy**: Redis para sesiones y datos frecuentes
- **File storage**: Local development, S3/similar para producción
- **Notifications**: Sistema unificado para todas las apps
- **Search**: Elasticsearch para búsquedas avanzadas (fase posterior)
- **API**: REST API para integraciones futuras (fase posterior)

---

**Fecha**: 2025-09-25
**Estado**: Documentación de diseño - Listo para iniciar desarrollo
**Próximo paso**: Configurar entorno de desarrollo expandido