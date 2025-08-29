# 👥 Agenda Académica - Test Users Documentation

## 📋 User List by Role

This document contains all test users created for the Agenda Académica system.

**Common Information:**
- 📧 **Email**: `jtorrecilla.unex@gmail.com` (all users)
- 🔑 **Password Pattern**: Same as the base name (without suffixes)

---

## 🔴 Admin Users

| Username | Password | Role | Email |
|----------|----------|------|-------|
| pablo | pablo | ADMIN | jtorrecilla.unex@gmail.com |
| marta | marta | ADMIN | jtorrecilla.unex@gmail.com |
| pedro | pedro | ADMIN | jtorrecilla.unex@gmail.com |
| antonio | antonio | ADMIN | jtorrecilla.unex@gmail.com |
| rufina | rufina | ADMIN | jtorrecilla.unex@gmail.com |
| blanca | blanca | ADMIN | jtorrecilla.unex@gmail.com |
| jose | jose | ADMIN | jtorrecilla.unex@gmail.com |

---

## 🟠 Coordinator Users

| Username | Password | Role | Email |
|----------|----------|------|-------|
| pablo_1 | pablo | COORDINATOR | jtorrecilla.unex@gmail.com |
| marta_1 | marta | COORDINATOR | jtorrecilla.unex@gmail.com |
| pedro_1 | pedro | COORDINATOR | jtorrecilla.unex@gmail.com |
| antonio_1 | antonio | COORDINATOR | jtorrecilla.unex@gmail.com |
| rufina_1 | rufina | COORDINATOR | jtorrecilla.unex@gmail.com |
| blanca_1 | blanca | COORDINATOR | jtorrecilla.unex@gmail.com |
| jose_1 | jose | COORDINATOR | jtorrecilla.unex@gmail.com |

---

## 🔵 Teacher Users

| Username | Password | Role | Email |
|----------|----------|------|-------|
| pablo_2 | pablo | TEACHER | jtorrecilla.unex@gmail.com |
| marta_2 | marta | TEACHER | jtorrecilla.unex@gmail.com |
| pedro_2 | pedro | TEACHER | jtorrecilla.unex@gmail.com |
| antonio_2 | antonio | TEACHER | jtorrecilla.unex@gmail.com |
| rufina_2 | rufina | TEACHER | jtorrecilla.unex@gmail.com |
| blanca_2 | blanca | TEACHER | jtorrecilla.unex@gmail.com |
| jose_2 | jose | TEACHER | jtorrecilla.unex@gmail.com |

---

## 🟢 Student Users

| Username | Password | Role | Email |
|----------|----------|------|-------|
| pablo_3 | pablo | STUDENT | jtorrecilla.unex@gmail.com |
| marta_3 | marta | STUDENT | jtorrecilla.unex@gmail.com |
| pedro_3 | pedro | STUDENT | jtorrecilla.unex@gmail.com |
| antonio_3 | antonio | STUDENT | jtorrecilla.unex@gmail.com |
| rufina_3 | rufina | STUDENT | jtorrecilla.unex@gmail.com |
| blanca_3 | blanca | STUDENT | jtorrecilla.unex@gmail.com |
| jose_3 | jose | STUDENT | jtorrecilla.unex@gmail.com |

---

## 📊 Summary

- **Total Users**: 28
- **Admin Users**: 7
- **Coordinator Users**: 7
- **Teacher Users**: 7
- **Student Users**: 7

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
*Last updated: 2025-08-29 12:07:43*
