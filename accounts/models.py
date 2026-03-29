from django.contrib.auth.models import AbstractUser
from django.db import models
from branches.models import Branch


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', 'مدير النظام'),
        ('branch_manager', 'مدير فرع'),
        ('employee', 'موظف'),
        ('regional_manager', 'مدير إقليمي'),  # إضافة هذا النوع
        ('accountant', 'محاسب'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='employee', verbose_name='نوع المستخدم')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الفرع')
    managed_branches = models.ManyToManyField(Branch, blank=True, related_name='regional_managers',
                                             verbose_name='الفروع التي يديرها')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    def has_custom_perm(self, perm_name):
        return self.has_perm(f'transactions.{perm_name}')  # مثال

    
    class Meta:
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمين'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_user_type_display()})"
    
    def is_branch_manager(self):
        return self.user_type == 'branch_manager'
    
    def is_admin(self):
        return self.user_type == 'admin'
    
    def get_unread_notifications_count(self):
        """عدد الإشعارات غير المقروءة"""
        return self.notifications.filter(is_read=False).count()


class Notification(models.Model):
    """نظام الإشعارات الداخلية"""
    
    NOTIFICATION_TYPES = [
        ('income', 'إيراد جديد'),
        ('expense', 'مصروف جديد'),
        ('installment', 'قسط مستحق'),
        ('registration', 'تسجيل جديد'),
        ('system', 'إشعار نظام'),
    ]
    
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name='المستلم'
    )
    
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES,
        verbose_name='نوع الإشعار'
    )
    
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    
    # بيانات إضافية للربط
    related_income = models.ForeignKey(
        'transactions.Income',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications',
        verbose_name='الإيراد المرتبط'
    )
    
    related_expense = models.ForeignKey(
        'transactions.Expense',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications',
        verbose_name='المصروف المرتبط'
    )
    
    related_student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='account_notifications',
        verbose_name='الطالب المرتبط'
    )
    
    # حالة الإشعار
    is_read = models.BooleanField(default=False, verbose_name='مقروء')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ القراءة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
