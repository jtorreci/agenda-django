## Project Status Recap

This document summarizes the current state of the Django application, highlighting implemented features, model changes, and areas for future development.

### Core Functionality

*   **User Authentication:** Implemented login, logout, and user registration.
*   **Role-Based Dashboards:** Basic dashboard views are in place for Teacher, Student, Coordinator, and Admin roles.

### Teacher Role Functionality

*   **Subject Management:** Teachers can select and manage their assigned subjects.
*   **Activity CRUD (Create, Read, Update, Delete):**
    *   **Create:** Teachers can create new activities linked to multiple selected subjects from their dashboard.
    *   **Read (Display):** Activities are displayed in a dynamic table on the teacher dashboard, filtered by currently selected subjects. Each activity appears uniquely, even if linked to multiple selected subjects.
    *   **Update:** Teachers can edit existing activities. The form pre-populates with the activity's data, and changes correctly update the existing activity (no duplication).
    *   **Soft Delete:** Activities are soft-deleted (their `activa` field is set to `False`) instead of being permanently removed from the database.
*   **iCal Feed Generation:**
    *   Teachers can create custom iCal feed configurations by selecting specific subjects and activity types.
    *   Unique iCal links are generated for each configuration and can be copied to the clipboard.
    *   The iCal feeds are functional, allowing external calendar applications to subscribe (with the understanding that `localhost` links require tunneling for external access).

### Model Changes

*   **`Actividad` Model Enhancements:**
    *   Added `evaluable` (Boolean), `porcentaje_evaluacion` (Decimal), `no_recuperable` (Boolean), `aprobada` (Boolean), and `activa` (Boolean) fields.
*   **New `LogActividad` Model:**
    *   Introduced a new model to log actions related to activities (e.g., creation, modification, deletion, approval).

### Form and View Enhancements

*   **Dynamic Form Filtering:**
    *   `ActividadForm` and `VistaCalendarioForm` dynamically filter subject choices based on the user's role (e.g., teachers only see their assigned subjects).
*   **Robust Activity Form:** The `activity_form` view correctly handles both creation and editing of activities, including pre-population of data for updates.
*   **Unique Activity Retrieval:** The `get_filtered_activities` view ensures that only unique activity objects are returned for display, preventing duplicate rows in the dashboard table.

### User Interface (UI)

*   **Teacher Dashboard:**
    *   Displays assigned subjects in a clear table with checkboxes for selection.
    *   Dynamically updates the activities table based on selected subjects.
    *   Includes a dedicated section for iCal feed configurations.
    *   `evaluable` and `aprobada` fields are displayed in the activities table (as checkboxes, `aprobada` is disabled).

### Database and Migrations

*   The database schema is up-to-date with all model changes, managed through Django migrations.

### Initial Data

*   A management command (`create_initial_activity_types`) is available to populate initial `TipoActividad` instances.

### Resolved Issues (during this session)

*   Numerous JavaScript syntax errors and indentation issues.
*   Incorrect URL generation for activity editing/deletion.
*   `NOT NULL` constraint failures due to schema mismatch.
*   `ActividadForm` not correctly pre-populating for editing.
*   Duplicate activity rows in the dashboard table.
*   `TipoActividad` field being empty in activity creation form.

### Outstanding/Future Considerations

*   **`LogActividad` Implementation:** The model is in place, but the logic to create log entries (on activity creation, modification, soft deletion, and approval) needs to be implemented in the relevant views.
*   **`activa` and `aprobada` Field Management:** While `activa` is handled on soft delete, and `aprobada` is read-only for teachers, the functionality for coordinators/administrators to change these fields (e.g., reactivate a deleted activity, approve an activity) needs to be developed.
*   **Student iCal Generation:** Adapt the iCal generation form and logic for students, allowing them to select any subject.
*   **Teacher Dashboard Table Merging:** The current table explicitly displays `Titulacion`, `Curso`, and `Semestre` per row. Implementing merged cells for these columns (as previously discussed) would require more complex Python-side data preparation to calculate `rowspan` values.
*   **Deployment:** For iCal links to work with external services, the application needs to be deployed to a public server or accessed via a tunneling service like `ngrok`.
