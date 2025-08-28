# User Manual: Agenda Académica

This manual provides a guide to using the Agenda Académica application, primarily focusing on the functionalities available to the **Teacher** role.

## 1. Introduction

Agenda Académica is a web application designed to help teachers manage their academic activities and share them with students via iCal feeds. It allows for the creation, management, and organization of activities linked to specific subjects.

## 2. Getting Started

### 2.1 Accessing the Application

To access the application, ensure the Django development server is running. You can usually start it by navigating to the project's root directory in your terminal and running:

```bash
python manage.py runserver
```

Once the server is running, open your web browser and go to `http://127.0.0.1:8000/` (or the address displayed in your terminal).

### 2.2 Login and Registration

*   **Registration:** If you are a new user, you will need to register for an account. Follow the on-screen instructions.
*   **Login:** Enter your credentials on the login page to access your dashboard.

## 3. Teacher Dashboard Overview

Upon logging in as a teacher, you will be directed to your dashboard. This dashboard is your central hub for managing your subjects and activities. It consists of three main sections:

*   **My Assigned Subjects:** A table listing the subjects you teach, with checkboxes to select them.
*   **Activities for Selected Subjects:** A dynamic table that displays activities associated with the subjects you have selected.
*   **iCal Feed Configurations:** A section to manage your personalized iCal feed links.

## 4. Coordinator Dashboard Overview

Upon logging in as a coordinator, you will be directed to your dashboard. This dashboard provides an overview of activities and allows for filtering and approval.

### 4.1 Dynamic Asignatura Filtering

The coordinator dashboard includes a filter form that allows you to narrow down the displayed activities. A key feature is the dynamic filtering of the 'Asignatura' (Subject) selector.

1.  **Select Titulaciones:** Choose one or more 'Titulaciones' (Degrees/Qualifications) from the multi-select dropdown.
2.  **Select Cursos:** Choose one or more 'Cursos' (Years/Courses) from the multi-select dropdown.
3.  **Dynamic Update:** As you select 'Titulaciones' and 'Cursos', the 'Asignatura' dropdown will automatically update to display only those subjects that are relevant to your selected degrees and courses. This helps in quickly finding and filtering activities for specific academic contexts.

After making your selections, you can click the 'Filter' button to apply all chosen filters to the activity list.

## 4. Managing Your Subjects

Before you can manage activities, you need to select the subjects you teach.

1.  On the Teacher Dashboard, click on the **"Select My Subjects"** link.
2.  On the subject selection page, choose your academic program (Titulacion) and then select the specific subjects you teach using the checkboxes.
3.  Click "Save" to update your assigned subjects.

## 5. Managing Activities

This section covers how to create, view, edit, and delete activities.

### 5.1 Viewing Activities

1.  On the Teacher Dashboard, in the **"My Assigned Subjects"** table, select one or more subjects using the checkboxes.
2.  The **"Activities for Selected Subjects"** table will automatically update to display all activities linked to any of your selected subjects. Each activity will appear only once.

### 5.2 Creating a New Activity

1.  In the **"My Assigned Subjects"** table, select the subjects you want to link the new activity to using the checkboxes.
2.  Click the **"Create Activity"** button located below the subject table.
    *   If no subjects are selected, an alert will prompt you to select at least one.
3.  You will be redirected to the activity creation form. The "Asignaturas" field will be pre-filled with your selected subjects.
4.  Fill in the activity details:
    *   **Name:** The name of the activity.
    *   **Subjects:** (Pre-selected from dashboard, but you can adjust if needed).
    *   **Activity Type:** Choose from predefined types (e.g., "Examen Parcial", "Práctica de Laboratorio").
    *   **Start Date/Time & End Date/Time:** Specify the activity's duration.
    *   **Description:** Optional details about the activity.
    *   **Evaluable:** Check this box if the activity counts towards a grade.
    *   **Percentage Evaluation:** If evaluable, specify its weight (e.g., 25.00 for 25%).
    *   **Non-Recoverable:** Check if the activity cannot be retaken.
5.  Click "Save" to create the activity. You will be redirected back to the dashboard.

### 5.3 Editing an Activity

1.  In the **"Activities for Selected Subjects"** table, locate the activity you wish to edit.
2.  Click the **"Edit"** button in the "Actions" column for that activity.
3.  You will be redirected to the activity form, pre-populated with the activity's current data.
4.  Make your desired changes to any of the fields.
5.  Click "Save" to update the activity. The changes will be reflected on the dashboard.

### 5.4 Deleting an Activity (Soft Delete)

1.  In the **"Activities for Selected Subjects"** table, locate the activity you wish to delete.
2.  Click the **"Delete"** button in the "Actions" column for that activity.
3.  You will be asked to confirm the deletion. Confirm to proceed.
    *   **Note:** Activities are not permanently removed. Instead, their `activa` status is set to `False`, making them invisible to teachers and students. Coordinators and administrators may have options to reactivate them.

## 6. Generating iCal Feeds

iCal feeds allow you to subscribe to your activities from external calendar applications (e.g., Google Calendar, Outlook).

### 6.1 Creating a New iCal Feed Configuration

1.  On the Teacher Dashboard, in the **"iCal Feed Configurations"** section, click the **"Create New iCal Feed"** link.
2.  On the form, provide a name for your feed.
3.  Select the subjects and activity types you want to include in this specific iCal feed.
4.  Click "Save" to create the configuration. You will be redirected back to the dashboard.

### 6.2 Copying and Using the iCal Link

1.  In the **"iCal Feed Configurations"** table on your dashboard, locate the feed you wish to use.
2.  Click the **"Copy iCal Link"** button in the "Actions" column.
3.  An alert will confirm that the link has been copied to your clipboard.
4.  Open your preferred calendar application (e.g., Google Calendar, Outlook, Apple Calendar).
5.  Look for an option to "Add Calendar by URL" or "Subscribe to Calendar".
6.  Paste the copied iCal link into the provided field.

**Important Note on Local Server:** If you are running the application on your local machine (`http://127.0.0.1:8000/`), external calendar services like Google Calendar will **not** be able to access your iCal feed directly. To test with external services, you would need to deploy your application to a public server or use a tunneling service like `ngrok` to expose your local server to the internet.

## 7. Important Notes

*   **Role-Based Access:** Different user roles (Teacher, Student, Coordinator, Administrator) have varying levels of access and functionality within the application.
*   **Support:** For any issues or questions, please contact your system administrator.
