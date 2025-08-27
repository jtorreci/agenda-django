# 🚀 Plan de Desarrollo MVP: Agenda Académica Inteligente (Parte 2)

---

## Fase 4: Documentación 📝

**Objetivo:** Crear una documentación clara y concisa para el proyecto, cubriendo tanto el uso como el desarrollo.

- [ ] **Documentación de Usuario:**
    - [ ] Crear un `README.md` actualizado en la raíz del proyecto con instrucciones de instalación, configuración y uso básico.
    - [ ] Documentar las funcionalidades principales (registro, login, dashboards de profesor/estudiante/coordinador, creación/edición/eliminación de actividades, panel de vistas de calendario, generación iCal).
- [ ] **Documentación Técnica (para desarrolladores):**
    - [ ] Documentar la estructura del proyecto (apps, modelos, vistas, formularios, URLs).
    - [ ] Explicar la lógica de asignación de roles por email.
    - [ ] Detallar el proceso de importación de datos iniciales.
    - [ ] Documentar la configuración del backend de email.

---

## Fase 5: Pruebas 🧪

**Objetivo:** Asegurar la calidad y el correcto funcionamiento de la aplicación mediante pruebas automatizadas.

- [ ] **Pruebas Unitarias:**
    - [ ] Escribir pruebas unitarias para los modelos (`CustomUser`, `Titulacion`, `Asignatura`, `TipoActividad`, `Actividad`, `VistaCalendario`).
    - [ ] Escribir pruebas unitarias para las funciones de vista críticas (registro, login, creación/edición/eliminación de actividades, generación iCal).
- [ ] **Pruebas de Integración:**
    - [ ] Probar la integración entre los diferentes módulos (ej. que un profesor pueda crear una actividad y un estudiante pueda verla).
    - [ ] Probar el flujo completo de registro y asignación de roles.
    - [ ] Probar la generación y suscripción del iCal.

---

## Fase 6: Estilizado del Frontend y Usabilidad ✨

**Objetivo:** Mejorar la interfaz de usuario y la experiencia general, haciendo la aplicación más atractiva y fácil de usar.

- [ ] **Integración de un Framework CSS:**
    - [ ] Integrar un framework CSS moderno (ej. Bootstrap) para un diseño responsivo y consistente.
    - [ ] Aplicar estilos básicos a todas las plantillas existentes.
- [ ] **Mejoras de Usabilidad:**
    - [ ] Añadir mensajes de éxito/error más amigables al usuario.
    - [ ] Mejorar la navegación entre las diferentes secciones de la aplicación.
    - [ ] Considerar la adición de un menú de navegación global.
- [ ] **Diseño de Formularios:**
    - [ ] Estilizar los formularios para que sean más atractivos y fáciles de usar.
    - [ ] Asegurar que los campos de fecha/hora sean intuitivos (ej. usando widgets de calendario si es posible).
