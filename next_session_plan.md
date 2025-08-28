# Next Session Plan

This plan outlines the work to be done in the upcoming session, building upon the current project status.

## Completed Features

*   **Dynamic Asignatura Filtering on Coordinator Dashboard:** Implemented dynamic filtering for the 'asignatura' selector based on 'titulaciones' and 'cursos' selections. This enhances the usability of the coordinator dashboard by providing relevant subject options.

## Phase 1: Implement Activity Logging (`LogActividad`)

**Goal:** To track and log significant actions performed on activities.

*   **Task 1.1: Log Activity Creation**
    *   **Location:** `schedule/views.py` (`activity_form` function, within the POST request for new activities).
    *   **Action:** After an activity is successfully created, create a `LogActividad` entry with `tipo_log='Creación'`, linking to the new activity and the current user.

*   **Task 1.2: Log Activity Modification**
    *   **Location:** `schedule/views.py` (`activity_form` function, within the POST request for existing activities).
    *   **Action:** After an activity is successfully updated, create a `LogActividad` entry with `tipo_log='Modificación'`, linking to the updated activity and the current user.

*   **Task 1.3: Log Activity Soft Deletion**
    *   **Location:** `schedule/views.py` (`activity_delete` function).
    *   **Action:** After an activity's `activa` status is set to `False`, create a `LogActividad` entry with `tipo_log='Borrado'`, linking to the activity and the current user.

*   **Task 1.4: (Future) Log Activity Approval**
    *   **Note:** This will be implemented once the approval mechanism for coordinators/administrators is in place.

*   **Task 1.5: View Activity Logs (Coordinator/Admin)**
    *   **Goal:** Provide a way for authorized users to see the activity history.
    *   **Action:** Create a new view and template (e.g., `schedule/activity_logs.html`) to display `LogActividad` entries. This view should be accessible only to Coordinators and Administrators.

## Phase 2: Coordinator/Admin Management of `activa` and `aprobada` Fields

**Goal:** To provide authorized users with the ability to manage critical activity statuses.

*   **Task 2.1: Reactivate Soft-Deleted Activities**
    *   **Action:** Create a view (e.g., `schedule/reactivate_activity`) that allows a Coordinator/Administrator to change an activity's `activa` status from `False` back to `True`.
    *   **Integration:** This could be a button in the `activity_logs` view or a separate management interface.
    *   **Logging:** Ensure a `LogActividad` entry is created for this action (e.g., `tipo_log='Reactivación'`).

*   **Task 2.2: Manage Activity Approval Status**
    *   **Action:** Create a view (e.g., `schedule/approve_activity`) that allows a Coordinator/Administrator to change an activity's `aprobada` status.
    *   **Integration:** Similar to reactivation, this could be a button in a management interface.
    *   **Logging:** Ensure a `LogActividad` entry is created for this action (e.g., `tipo_log='Aprobación'` or `tipo_log='Desaprobación'`).

## Phase 3: Student iCal Generation

**Goal:** To enable students to generate iCal feeds for activities relevant to them.

*   **Task 3.1: Student iCal Form and View**
    *   **Location:** Consider creating a new view (e.g., `users/student_ical_config`) and template for students.
    *   **Action:** Adapt the `VistaCalendarioForm` logic to allow students to select *any* subject (as opposed to only their assigned ones, which is the current teacher behavior).
    *   **Integration:** Add a link to this new view on the student dashboard.

## Phase 4: Implement Spanish Interface (Internationalization)

**Goal:** To provide the application interface in Spanish.

*   **Task 4.1: Configure Django for i18n**
    *   **Action:** Modify `settings.py` to enable internationalization, set `LANGUAGE_CODE` to `es`, and configure `LOCALE_PATHS`.

*   **Task 4.2: Mark Strings for Translation**
    *   **Action:** Go through templates and Python code, wrapping user-facing strings with `gettext` or `gettext_lazy`.

*   **Task 4.3: Generate Message Files**
    *   **Action:** Run `python manage.py makemessages -l es` to create `.po` files.

*   **Task 4.4: Translate Strings**
    *   **Action:** Manually translate strings in the generated `.po` files.

*   **Task 4.5: Compile Message Files**
    *   **Action:** Run `python manage.py compilemessages` to create `.mo` files.

## Phase 5: UI/UX Improvements (Optional, based on time/priority)

**Goal:** To enhance the user experience and visual presentation.

*   **Task 5.1: Teacher Dashboard Table Merging**
    *   **Action:** Revisit the teacher dashboard's subject table to implement merged cells for `Titulacion`, `Curso`, and `Semestre` (if still desired).
    *   **Approach:** This would likely involve preparing the data with `rowspan` values in the Python view before passing it to the template, rather than complex template logic.

*   **Task 5.2: Date/Time Picker Integration**
    *   **Action:** Integrate a user-friendly date/time picker library into the `ActividadForm` to improve the input experience for `fecha_inicio` and `fecha_fin`.

## Phase 6: Testing and Refinement

**Goal:** To ensure the stability, correctness, and quality of the new features.

*   **Task 6.1: Comprehensive Testing**
    *   Thoroughly test all newly implemented functionalities across different user roles.
    *   Pay special attention to edge cases and error handling.

*   **Task 6.2: Code Cleanup and Refactoring**
    *   Review and refactor code for readability, maintainability, and adherence to best practices.
    *   Remove any temporary `console.log` statements or debugging code.
