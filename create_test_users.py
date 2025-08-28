#!/usr/bin/env python
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
django.setup()

from django.contrib.auth import get_user_model
from academics.models import Titulacion, Asignatura

User = get_user_model()

def create_test_users():
    """Create test users for each role with predefined credentials"""
    
    # Admin user
    if not User.objects.filter(username='admin_test').exists():
        admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@unex.es',
            password='admin123',
            first_name='Admin',
            last_name='Test',
            role=User.ROLE_ADMIN
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        print("✓ Admin user created: admin_test / admin123")
    else:
        print("! Admin user already exists")

    # Coordinator user
    if not User.objects.filter(username='coord_test').exists():
        coord_user = User.objects.create_user(
            username='coord_test',
            email='coordinador@unex.es',
            password='coord123',
            first_name='Carlos',
            last_name='Coordinador',
            role=User.ROLE_COORDINATOR
        )
        print("✓ Coordinator user created: coord_test / coord123")
    else:
        print("! Coordinator user already exists")

    # Teacher users
    teachers_data = [
        {
            'username': 'prof_mate',
            'email': 'matematicas@unex.es',
            'password': 'mate123',
            'first_name': 'María',
            'last_name': 'Matemática'
        },
        {
            'username': 'prof_fisica',
            'email': 'fisica@unex.es',
            'password': 'fisica123',
            'first_name': 'Pedro',
            'last_name': 'Físico'
        },
        {
            'username': 'prof_quimica',
            'email': 'quimica@unex.es',
            'password': 'quimica123',
            'first_name': 'Ana',
            'last_name': 'Química'
        }
    ]

    for teacher_data in teachers_data:
        if not User.objects.filter(username=teacher_data['username']).exists():
            teacher_user = User.objects.create_user(
                username=teacher_data['username'],
                email=teacher_data['email'],
                password=teacher_data['password'],
                first_name=teacher_data['first_name'],
                last_name=teacher_data['last_name'],
                role=User.ROLE_TEACHER
            )
            print(f"✓ Teacher user created: {teacher_data['username']} / {teacher_data['password']}")
        else:
            print(f"! Teacher user {teacher_data['username']} already exists")

    # Student users
    students_data = [
        {
            'username': 'alumno1',
            'email': 'estudiante1@alumnos.unex.es',
            'password': 'alumno123',
            'first_name': 'Juan',
            'last_name': 'Estudiante'
        },
        {
            'username': 'alumno2',
            'email': 'estudiante2@alumnos.unex.es',
            'password': 'alumno123',
            'first_name': 'Laura',
            'last_name': 'Alumna'
        },
        {
            'username': 'alumno3',
            'email': 'estudiante3@alumnos.unex.es',
            'password': 'alumno123',
            'first_name': 'Diego',
            'last_name': 'Escolar'
        }
    ]

    for student_data in students_data:
        if not User.objects.filter(username=student_data['username']).exists():
            student_user = User.objects.create_user(
                username=student_data['username'],
                email=student_data['email'],
                password=student_data['password'],
                first_name=student_data['first_name'],
                last_name=student_data['last_name'],
                role=User.ROLE_STUDENT
            )
            print(f"✓ Student user created: {student_data['username']} / {student_data['password']}")
        else:
            print(f"! Student user {student_data['username']} already exists")

    print("\n" + "="*60)
    print("TEST USERS SUMMARY:")
    print("="*60)
    print("ADMIN:")
    print("  Username: admin_test")
    print("  Password: admin123")
    print("  Email: admin@unex.es")
    print()
    print("COORDINATOR:")
    print("  Username: coord_test")
    print("  Password: coord123")
    print("  Email: coordinador@unex.es")
    print()
    print("TEACHERS:")
    for teacher in teachers_data:
        print(f"  Username: {teacher['username']}")
        print(f"  Password: {teacher['password']}")
        print(f"  Email: {teacher['email']}")
        print()
    print("STUDENTS:")
    for student in students_data:
        print(f"  Username: {student['username']}")
        print(f"  Password: {student['password']}")
        print(f"  Email: {student['email']}")
        print()

if __name__ == '__main__':
    create_test_users()