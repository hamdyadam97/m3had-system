from django.db import models
from branches.models import Branch
from courses.models import Course


class Student(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'كاش'),
        ('installment', 'قسط'),
    ]
    
    PAYMENT_LOCATION_CHOICES = [
        ('in_person', 'حضوري'),
        ('remote', 'عن بعد'),
    ]
    
    full_name = models.CharField(max_length=200, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    national_id = models.CharField(max_length=20, blank=True, verbose_name='رقم البطاقة')
    address = models.TextField(blank=True, verbose_name='العنوان')
    
    # بيانات التسجيل
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='الدورة/الدبلومة')
    registration_date = models.DateField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    
    # بيانات الدفع
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر الإجمالي')
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, verbose_name='طريقة الدفع')
    payment_location = models.CharField(max_length=10, choices=PAYMENT_LOCATION_CHOICES, default='in_person', verbose_name='مكان الدفع')
    
    # للأقساط - عدد الأقساط يُختار عند التسجيل
    installment_count = models.PositiveIntegerField(default=1, verbose_name='عدد الأقساط')
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='قيمة القسط')
    first_installment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ أول قسط')
    paid_installments = models.PositiveIntegerField(default=0, verbose_name='الأقساط المدفوعة')
    
    # للتحويل البنكي
    bank_account_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الحساب البنكي (للتحويل)')
    
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'
        ordering = ['-registration_date']
    
    def __str__(self):
        return f"{self.full_name} - {self.course.name}"
    
    def get_remaining_amount(self):
        """المبلغ المتبقي للطالب"""
        from transactions.models import Income
        total_paid = Income.objects.filter(
            student=self,
            income_type='installment'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return self.total_price - total_paid
    
    def get_total_paid(self):
        """إجمالي المدفوع"""
        from transactions.models import Income
        total = Income.objects.filter(
            student=self
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        return total
    
    def is_fully_paid(self):
        """هل تم دفع المبلغ كاملاً؟"""
        return self.get_remaining_amount() <= 0
    
    def get_payment_status(self):
        """حالة الدفع"""
        remaining = self.get_remaining_amount()
        if remaining <= 0:
            return 'مدفوع بالكامل'
        elif self.get_total_paid() > 0:
            return f'متبقي {remaining:,.2f}'
        return 'غير مدفوع'
    
    def has_overdue_installments(self):
        """هل يوجد أقساط متأخرة؟"""
        if hasattr(self, 'installment_plan'):
            return self.installment_plan.has_overdue_installments()
        return False
    
    def get_overdue_days(self):
        """عدد أيام التأخر للأقساط المتأخرة"""
        if hasattr(self, 'installment_plan'):
            overdue = self.installment_plan.get_overdue_installments().first()
            if overdue:
                return overdue.days_overdue()
        return 0
    
    def get_payment_status_class(self):
        """فئة CSS لحالة الدفع (للتلوين في القوائم)"""
        if self.has_overdue_installments():
            return 'danger'  # أحمر للمتأخرين
        elif self.is_fully_paid():
            return 'success'  # أخضر للمدفوع
        elif self.get_total_paid() > 0:
            return 'warning'  # أصفر للمدفوع جزئياً
        return 'secondary'  # رمادي للغير مدفوع


# استيراد النماذج الإضافية
from .installment_models import InstallmentPlan, Installment
from .notification_models import NotificationSettings, NotificationLog

# إضافة خاصية للنموذج للوصول السريع
Student.installment_plan = property(lambda self: getattr(self, '_installment_plan', None))
