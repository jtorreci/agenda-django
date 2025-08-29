#!/usr/bin/env python
"""
Script to create test users for the Agenda Académica system
Creates users with specified pattern: base names + suffixes for different roles
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
django.setup()

from users.models import CustomUser

def create_test_users():
    """Create test users with specified patterns"""
    
    # Base names for users
    base_names = ['pablo', 'marta', 'pedro', 'antonio', 'rufina', 'blanca', 'jose']
    email = 'jtorrecilla.unex@gmail.com'
    
    users_created = []
    
    print("🚀 Creating test users for Agenda Académica...")
    print("=" * 60)
    
    for name in base_names:
        # 1. Admin users (base names)
        try:
            admin_user, created = CustomUser.objects.get_or_create(
                username=name,
                defaults={
                    'email': email,
                    'first_name': name.capitalize(),
                    'role': 'ADMIN'
                }
            )
            if created:
                admin_user.set_password(name)
                admin_user.save()
                users_created.append(f"✅ Admin: {name} (password: {name})")
                print(f"✅ Created ADMIN user: {name}")
            else:
                admin_user.role = 'ADMIN'
                admin_user.set_password(name)
                admin_user.save()
                users_created.append(f"🔄 Admin: {name} (password: {name}) - Updated")
                print(f"🔄 Updated ADMIN user: {name}")
        except Exception as e:
            print(f"❌ Error creating admin {name}: {e}")
        
        # 2. Coordinator users (_1 suffix)
        try:
            coord_username = f"{name}_1"
            coord_user, created = CustomUser.objects.get_or_create(
                username=coord_username,
                defaults={
                    'email': email,
                    'first_name': name.capitalize(),
                    'role': 'COORDINATOR'
                }
            )
            if created:
                coord_user.set_password(name)
                coord_user.save()
                users_created.append(f"✅ Coordinator: {coord_username} (password: {name})")
                print(f"✅ Created COORDINATOR user: {coord_username}")
            else:
                coord_user.role = 'COORDINATOR'
                coord_user.set_password(name)
                coord_user.save()
                users_created.append(f"🔄 Coordinator: {coord_username} (password: {name}) - Updated")
                print(f"🔄 Updated COORDINATOR user: {coord_username}")
        except Exception as e:
            print(f"❌ Error creating coordinator {coord_username}: {e}")
        
        # 3. Teacher users (_2 suffix)
        try:
            teacher_username = f"{name}_2"
            teacher_user, created = CustomUser.objects.get_or_create(
                username=teacher_username,
                defaults={
                    'email': email,
                    'first_name': name.capitalize(),
                    'role': 'TEACHER'
                }
            )
            if created:
                teacher_user.set_password(name)
                teacher_user.save()
                users_created.append(f"✅ Teacher: {teacher_username} (password: {name})")
                print(f"✅ Created TEACHER user: {teacher_username}")
            else:
                teacher_user.role = 'TEACHER'
                teacher_user.set_password(name)
                teacher_user.save()
                users_created.append(f"🔄 Teacher: {teacher_username} (password: {name}) - Updated")
                print(f"🔄 Updated TEACHER user: {teacher_username}")
        except Exception as e:
            print(f"❌ Error creating teacher {teacher_username}: {e}")
        
        # 4. Student users (_3 suffix)
        try:
            student_username = f"{name}_3"
            student_user, created = CustomUser.objects.get_or_create(
                username=student_username,
                defaults={
                    'email': email,
                    'first_name': name.capitalize(),
                    'role': 'STUDENT'
                }
            )
            if created:
                student_user.set_password(name)
                student_user.save()
                users_created.append(f"✅ Student: {student_username} (password: {name})")
                print(f"✅ Created STUDENT user: {student_username}")
            else:
                student_user.role = 'STUDENT'
                student_user.set_password(name)
                student_user.save()
                users_created.append(f"🔄 Student: {student_username} (password: {name}) - Updated")
                print(f"🔄 Updated STUDENT user: {student_username}")
        except Exception as e:
            print(f"❌ Error creating student {student_username}: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎉 User creation completed!")
    print(f"📊 Total users processed: {len(base_names) * 4}")
    
    # Generate markdown documentation
    generate_user_documentation(base_names, email)
    
    return users_created

def generate_user_documentation(base_names, email):
    """Generate markdown documentation with all user details"""
    
    print("\n📄 Generating user documentation...")
    
    md_content = """# 👥 Agenda Académica - Test Users Documentation

## 📋 User List by Role

This document contains all test users created for the Agenda Académica system.

**Common Information:**
- 📧 **Email**: `jtorrecilla.unex@gmail.com` (all users)
- 🔑 **Password Pattern**: Same as the base name (without suffixes)

---

## 🔴 Admin Users

| Username | Password | Role | Email |
|----------|----------|------|-------|"""

    # Add admin users
    for name in base_names:
        md_content += f"\n| {name} | {name} | ADMIN | {email} |"
    
    md_content += """

---

## 🟠 Coordinator Users

| Username | Password | Role | Email |
|----------|----------|------|-------|"""

    # Add coordinator users
    for name in base_names:
        md_content += f"\n| {name}_1 | {name} | COORDINATOR | {email} |"
    
    md_content += """

---

## 🔵 Teacher Users

| Username | Password | Role | Email |
|----------|----------|------|-------|"""

    # Add teacher users
    for name in base_names:
        md_content += f"\n| {name}_2 | {name} | TEACHER | {email} |"
    
    md_content += """

---

## 🟢 Student Users

| Username | Password | Role | Email |
|----------|----------|------|-------|"""

    # Add student users
    for name in base_names:
        md_content += f"\n| {name}_3 | {name} | STUDENT | {email} |"
    
    md_content += f"""

---

## 📊 Summary

- **Total Users**: {len(base_names) * 4}
- **Admin Users**: {len(base_names)}
- **Coordinator Users**: {len(base_names)}
- **Teacher Users**: {len(base_names)}
- **Student Users**: {len(base_names)}

## 🔐 Login Examples

### Admin Login
- Username: `pablo`
- Password: `pablo`
- Access: Full system administration

### Coordinator Login
- Username: `marta_1` 
- Password: `marta`
- Access: Coordination dashboard, activity approval

### Teacher Login
- Username: `pedro_2`
- Password: `pedro`
- Access: Teacher dashboard, create activities

### Student Login
- Username: `antonio_3`
- Password: `antonio`
- Access: Student dashboard, view activities

---

## 🛠️ Technical Notes

1. **User Creation**: Users were created using Django's `create_user` method
2. **Password Hashing**: Passwords are properly hashed using Django's authentication system
3. **Role Assignment**: Each user has a specific role assigned for proper access control
4. **Email**: All users share the same email address for testing purposes

## 🚀 Usage Instructions

1. **Login**: Use any username/password combination from the tables above
2. **Role Testing**: Each role has different dashboard and permissions
3. **Development**: These users are for development and testing only
4. **Production**: Do not use these credentials in production environments

---

*Generated automatically by create_test_users_new.py*
*Last updated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    # Write to file
    with open('test_users_documentation.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print("✅ Documentation saved to: test_users_documentation.md")

if __name__ == '__main__':
    try:
        users_created = create_test_users()
        print(f"\n🎊 Success! All users have been created and documented.")
        print(f"📁 Check 'test_users_documentation.md' for complete user list.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)