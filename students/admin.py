from django.contrib import admin
from .models import Student, InstallmentPlan, Installment, NotificationSettings, NotificationLog


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    readonly_fields = ['installment_number', 'amount', 'due_date', 'is_paid', 'paid_date', 'get_status_display']
    fields = ['installment_number', 'amount', 'due_date', 'is_paid', 'paid_date', 'get_status_display']
    can_delete = False
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    get_status_display.short_description = 'الحالة'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'branch', 'course', 'payment_method', 'total_price', 'get_payment_status', 'has_overdue_status', 'registration_date']
    list_filter = ['branch', 'course', 'payment_method', 'payment_location', 'is_active']
    search_fields = ['full_name', 'phone', 'national_id']
    readonly_fields = ['created_at', 'updated_at', 'get_total_paid', 'get_remaining_amount']
    
    def get_payment_status(self, obj):
        return obj.get_payment_status()
    get_payment_status.short_description = 'حالة الدفع'
    
    def has_overdue_status(self, obj):
        if obj.has_overdue_installments():
            days = obj.get_overdue_days()
            return f"⚠️ متأخر {days} يوم"
        return "✓"
    has_overdue_status.short_description = 'التأخر'


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    list_display = ['student', 'total_amount', 'number_of_installments', 'get_paid_count', 'get_remaining_count', 'first_installment_date']
    list_filter = ['number_of_installments']
    search_fields = ['student__full_name', 'student__phone']
    readonly_fields = ['created_at']
    inlines = [InstallmentInline]
    
    def get_paid_count(self, obj):
        return obj.get_paid_count()
    get_paid_count.short_description = 'المدفوع'
    
    def get_remaining_count(self, obj):
        return obj.get_remaining_count()
    get_remaining_count.short_description = 'المتبقي'


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ['installment_number', 'plan', 'amount', 'due_date', 'is_paid', 'get_status_display', 'days_until_due']
    list_filter = ['is_paid', 'due_date']
    search_fields = ['plan__student__full_name', 'plan__student__phone']
    readonly_fields = ['created_at']
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    get_status_display.short_description = 'الحالة'
    
    def days_until_due(self, obj):
        days = obj.days_until_due()
        if days is None:
            return "-"
        if days < 0:
            return f"متأخر {-days} يوم"
        return f"بعد {days} يوم"
    days_until_due.short_description = 'الوقت المتبقي'


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ['email_enabled', 'whatsapp_enabled', 'contact_phone', 'updated_at']
    
    def has_add_permission(self, request):
        # السماح بإنشاء واحد فقط
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['student', 'installment', 'get_notification_type_display', 'notification_reason', 'recipient', 'status', 'created_at']
    list_filter = ['notification_type', 'status', 'created_at']
    search_fields = ['student__full_name', 'recipient', 'message']
    readonly_fields = ['created_at']
