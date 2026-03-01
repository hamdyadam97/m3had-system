from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'user_type', 'branch', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_active', 'branch']
    search_fields = ['username', 'first_name', 'last_name', 'phone']
    
    fieldsets = UserAdmin.fieldsets + (
        ('معلومات إضافية', {
            'fields': ('user_type', 'branch', 'phone'),
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('معلومات إضافية', {
            'fields': ('user_type', 'branch', 'phone'),
        }),
    )
