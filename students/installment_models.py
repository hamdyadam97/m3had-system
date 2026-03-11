from django.db import models
from django.utils import timezone
from .models import Student


class InstallmentPlan(models.Model):
    """خطة تقسيط للطالب"""
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='installment_plan', verbose_name='الطالب')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ الإجمالي')
    number_of_installments = models.PositiveIntegerField(verbose_name='عدد الأقساط')
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='قيمة القسط')
    first_installment_date = models.DateField(verbose_name='تاريخ أول قسط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'خطة تقسيط'
        verbose_name_plural = 'خطط التقسيط'
    
    def __str__(self):
        return f"{self.student.full_name} - {self.number_of_installments} قسط"
    
    def create_installments(self):
        """إنشاء الأقساط بناءً على الخطة"""
        from dateutil.relativedelta import relativedelta
        
        # حذف الأقساط القديمة إن وجدت
        self.installments.all().delete()
        
        # إنشاء الأقساط الجديدة
        for i in range(self.number_of_installments):
            due_date = self.first_installment_date + relativedelta(months=i)
            Installment.objects.create(
                plan=self,
                installment_number=i + 1,
                amount=self.installment_amount,
                due_date=due_date
            )
    
    def get_paid_count(self):
        """عدد الأقساط المدفوعة"""
        return self.installments.filter(is_paid=True).count()
    
    def get_remaining_count(self):
        """عدد الأقساط المتبقية"""
        return self.number_of_installments - self.get_paid_count()
    
    def get_total_paid(self):
        """إجمالي المدفوع"""
        return self.installments.filter(is_paid=True).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
    
    def get_next_installment(self):
        """القسط القادم غير المدفوع"""
        return self.installments.filter(is_paid=False).order_by('due_date').first()
    
    def has_overdue_installments(self):
        """هل يوجد أقساط متأخرة؟"""
        today = timezone.now().date()
        return self.installments.filter(is_paid=False, due_date__lt=today).exists()
    
    def get_overdue_installments(self):
        """الأقساط المتأخرة"""
        today = timezone.now().date()
        return self.installments.filter(is_paid=False, due_date__lt=today).order_by('due_date')


class Installment(models.Model):
    """قسط فردي"""
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='installments', verbose_name='خطة التقسيط')
    installment_number = models.PositiveIntegerField(verbose_name='رقم القسط')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ')
    due_date = models.DateField(verbose_name='تاريخ الاستحقاق')
    is_paid = models.BooleanField(default=False, verbose_name='مدفوع')
    paid_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الدفع')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المبلغ المدفوع')
    
    # حالة الإشعارات
    reminder_sent_2days = models.BooleanField(default=False, verbose_name='تم إرسال تذكير قبل يومين')
    reminder_sent_1day = models.BooleanField(default=False, verbose_name='تم إرسال تذكير قبل يوم')
    reminder_sent_due = models.BooleanField(default=False, verbose_name='تم إرسال تذكير يوم الاستحقاق')
    overdue_notice_sent = models.BooleanField(default=False, verbose_name='تم إرسال إشعار التأخر')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'قسط'
        verbose_name_plural = 'الأقساط'
        ordering = ['installment_number']
    
    def __str__(self):
        return f"القسط {self.installment_number} - {self.plan.student.full_name}"
    
    def get_status(self):
        """حالة القسط"""
        if self.is_paid:
            return 'paid'
        
        today = timezone.now().date()
        
        if self.due_date < today:
            return 'overdue'  # متأخر
        elif self.due_date == today:
            return 'due_today'  # مستحق اليوم
        elif (self.due_date - today).days <= 2:
            return 'due_soon'  # قريب
        else:
            return 'pending'  # معلق
    
    def get_status_display(self):
        """نص حالة القسط"""
        status = self.get_status()
        status_map = {
            'paid': 'مدفوع',
            'overdue': 'متأخر',
            'due_today': 'مستحق اليوم',
            'due_soon': 'مستحق قريباً',
            'pending': 'معلق'
        }
        return status_map.get(status, 'غير معروف')
    
    def get_status_color(self):
        """لون حالة القسط"""
        status = self.get_status()
        color_map = {
            'paid': 'success',
            'overdue': 'danger',
            'due_today': 'warning',
            'due_soon': 'info',
            'pending': 'secondary'
        }
        return color_map.get(status, 'secondary')
    
    def days_until_due(self):
        """عدد الأيام حتى تاريخ الاستحقاق"""
        if self.is_paid:
            return None
        today = timezone.now().date()
        return (self.due_date - today).days
    
    def days_overdue(self):
        """عدد أيام التأخر"""
        if self.is_paid:
            return 0
        today = timezone.now().date()
        if self.due_date < today:
            return (today - self.due_date).days
        return 0
