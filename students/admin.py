from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'branch', 'course', 'payment_method', 'total_price', 'get_payment_status', 'registration_date']
    list_filter = ['branch', 'course', 'payment_method', 'payment_location', 'is_active']
    search_fields = ['full_name', 'phone', 'national_id']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_payment_status(self, obj):
        return obj.get_payment_status()
    get_payment_status.short_description = 'حالة الدفع'
