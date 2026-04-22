from django.db import models
from branches.models import Branch


class MonthlyReport(models.Model):
    """تقرير شهري لكل فرع"""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    year = models.PositiveIntegerField(verbose_name='السنة')
    month = models.PositiveIntegerField(verbose_name='الشهر')
    
    # الأهداف
    monthly_target = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='الهدف الشهري')
    
    # الإيرادات
    total_registration_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إيرادات التسجيل')
    total_installment_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إيرادات التحصيل')
    total_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إجمالي الإيرادات')
    
    # المصروفات
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إجمالي المصروفات')
    
    # الصافي والربح
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='الصافي')
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='الربح')
    
    # نسبة الإنجاز
    achievement_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الإنجاز %')
    
    # الإحصائيات
    new_students_count = models.PositiveIntegerField(default=0, verbose_name='عدد الطلاب الجدد')
    total_students_count = models.PositiveIntegerField(default=0, verbose_name='إجمالي عدد الطلاب')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقرير شهري'
        verbose_name_plural = 'التقارير الشهرية'
        ordering = ['-year', '-month']
        unique_together = ['branch', 'year', 'month']
    
    def __str__(self):
        return f"{self.branch.name} - {self.month}/{self.year}"


class EmployeeReport(models.Model):
    """تقرير أداء الموظفين"""
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, verbose_name='الموظف')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    date = models.DateField(verbose_name='التاريخ')
    
    # الإحصائيات
    registrations_count = models.PositiveIntegerField(default=0, verbose_name='عدد التسجيلات')
    installments_count = models.PositiveIntegerField(default=0, verbose_name='عدد التحصيلات')
    total_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إجمالي المحصل')
    
    # تفاصيل
    cash_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='كاش')
    visa_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='فيزا')
    bank_transfer_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='تحويل بنكي')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقرير موظف'
        verbose_name_plural = 'تقارير الموظفين'
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.date} - {self.total_collected:,.2f}"
