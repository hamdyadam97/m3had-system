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
