from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['email', 'username', 'is_staff', 'role'] # Added 'role' for easier viewing
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'subjects', 'coordinated_titulaciones',)}), # Added 'role', 'subjects', 'coordinated_titulaciones'
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role', 'subjects', 'coordinated_titulaciones',)}), # Added 'role', 'subjects', 'coordinated_titulaciones'
    )

admin.site.register(CustomUser, CustomUserAdmin)