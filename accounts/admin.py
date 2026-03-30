from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from .models import User, Notification


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # الحقول المعروضة في قائمة المستخدمين
    list_display = [
        'username', 'get_full_name', 'email', 'user_type', 
        'branch', 'get_groups', 'is_active', 'date_joined'
    ]
    
    # الفلاتر الجانبية
    list_filter = [
        'user_type', 'is_active', 'branch', 'groups', 
        'date_joined', 'is_superuser'
    ]
    
    # حقول البحث
    search_fields = [
        'username', 'first_name', 'last_name', 'email', 
        'phone', 'branch__name', 'user_type'
    ]
    
    # الترتيب الافتراضي
    ordering = ['-date_joined']
    
    # عدد العناصر في الصفحة
    list_per_page = 25
    
    # حقول قابلة للتعديل مباشرة في القائمة
    list_editable = ['is_active']
    
    # إظهار حقول إضافية في صفحة التفاصيل
    fieldsets = UserAdmin.fieldsets + (
        ('معلومات إضافية', {
            'fields': ('user_type', 'branch', 'phone', 'managed_branches'),
        }),
    )
    
    # إظهار نفس الحقول عند إضافة مستخدم جديد
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('معلومات إضافية', {
            'fields': ('user_type', 'branch', 'phone'),
        }),
    )
    
    # تحسين عرض الحقول المتعددة
    filter_horizontal = ['groups', 'user_permissions', 'managed_branches']
    
    # تحسين عرض البحث
    def get_search_results(self, request, queryset, search_term):
        """
        تحسين البحث ليدعم البحث بالاسم الكامل والبريد الإلكتروني
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            # البحث بالاسم الكامل (دمج الاسم الأول والأخير)
            queryset |= self.model.objects.filter(
                Q(first_name__icontains=search_term) | 
                Q(last_name__icontains=search_term) |
                Q(email__icontains=search_term)
            )
        
        return queryset, use_distinct
    
    # دالة مساعدة لعرض الاسم الكامل
    @admin.display(description='الاسم الكامل')
    def get_full_name(self, obj):
        return obj.get_full_name() or '-'
    
    # دالة مساعدة لعرض المجموعات
    @admin.display(description='مجموعات الصلاحيات')
    def get_groups(self, obj):
        return ', '.join([g.name for g in obj.groups.all()]) or '-'
    
    # تحسين عرض اسم الفرع
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch":
            kwargs["empty_label"] = "اختر الفرع"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # إضافة أزرار إجراءات مخصصة
    actions = ['activate_users', 'deactivate_users', 'make_staff', 'remove_staff']
    
    @admin.action(description='تفعيل المستخدمين المحددين')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
    
    @admin.action(description='تعطيل المستخدمين المحددين')
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    
    @admin.action(description='منح صلاحية موظف (staff)')
    def make_staff(self, request, queryset):
        queryset.update(is_staff=True)
    
    @admin.action(description='إلغاء صلاحية موظف (staff)')
    def remove_staff(self, request, queryset):
        queryset.update(is_staff=False)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """إدارة الإشعارات الداخلية"""
    
    list_display = [
        'title', 'recipient', 'notification_type', 
        'is_read', 'created_at', 'read_at'
    ]
    list_filter = [
        'notification_type', 'is_read', 'created_at'
    ]
    search_fields = [
        'title', 'message', 'recipient__username', 
        'recipient__first_name', 'recipient__last_name'
    ]
    list_editable = ['is_read']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('معلومات أساسية', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('الروابط المرتبطة', {
            'fields': ('related_income', 'related_expense', 'related_student'),
            'classes': ('collapse',)
        }),
        ('حالة الإشعار', {
            'fields': ('is_read', 'read_at', 'created_at')
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    @admin.action(description='تحديد كمقروء')
    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_read=True, read_at=timezone.now())
    
    @admin.action(description='تحديد كغير مقروء')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None)
