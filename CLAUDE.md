# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an academic agenda Django application that manages activities, subjects, and users for educational institutions. The project implements role-based access control with four user types: Students, Teachers, Coordinators, and Admins.

## Development Commands

- **Run development server**: `python manage.py runserver`
- **Run migrations**: `python manage.py migrate` 
- **Create migrations**: `python manage.py makemigrations`
- **Create superuser**: `python manage.py createsuperuser`
- **Import initial data**: `python manage.py importdata`
- **Create initial activity types**: `python manage.py create_initial_activity_types`
- **Django shell**: `python manage.py shell`

## Database

- Uses SQLite3 database (`db.sqlite3`)
- Custom user model: `users.CustomUser` with role-based access
- Main models: `Actividad` (Activity), `Asignatura` (Subject), `Titulacion` (Degree), `TipoActividad` (Activity Type)

## Project Architecture

### Apps Structure

- **`users/`**: Authentication, user roles (Student, Teacher, Coordinator, Admin), dashboards
- **`academics/`**: Academic data models - `Titulacion` and `Asignatura` with course/semester organization
- **`schedule/`**: Activity management, calendar views, iCal feed generation, activity logging
- **`agenda_academica/`**: Main project app with settings management and shared views

### Key Models Relationships

- `CustomUser` has `ManyToManyField` to `Asignatura` (subjects) and `Titulacion` (coordinated degrees)
- `Asignatura` belongs to `Titulacion` and has course/semester fields
- `Actividad` has `ManyToManyField` to `Asignatura` and `ForeignKey` to `TipoActividad`
- `VistaCalendario` allows users to create custom iCal feeds with filtered subjects/activity types
- `LogActividad` tracks all activity-related actions with timestamps

### Role-Based Features

- **Teachers**: Manage activities for their assigned subjects, create iCal feeds
- **Students**: View activities for their subjects, generate personalized calendars
- **Coordinators**: Approve activities, manage subjects within their coordinated degrees
- **Admins**: Full system access

## Important Implementation Details

- Activities use soft deletion (`activa` field) instead of permanent deletion
- Dynamic form filtering based on user roles and selected criteria
- AJAX endpoints for cascading dropdowns (titulaciones → cursos → asignaturas)
- iCal feed generation with UUID tokens for security
- Activity logging system tracks creation, modification, deletion, and approval actions
- Spanish localization (`LANGUAGE_CODE = 'es'`)

## Development Notes

- Template directories include both root `templates/` and `schedule/templates/`
- Uses Django's built-in authentication with custom user model
- Email backend configured for console output during development
- All forms implement dynamic filtering based on user permissions and selections
- Activities table displays unique entries even when linked to multiple subjects

## Custom Management Commands

Located in `agenda_academica/management/commands/`:
- `importdata.py`: Import academic data from CSV files
- `create_initial_activity_types.py`: Populate initial activity types