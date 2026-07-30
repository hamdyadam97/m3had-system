from django.db import models
from accounts.models import User
from branches.models import Branch
from courses.models import Course


class Income(models.Model):
    INCOME_TYPE_CHOICES = [
        ('registration', 'تسجيل جديد'),
        ('installment', 'تحصيل قسط'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mada', 'مدى'),
        ('bank_transfer', 'بنك'),
        ('cash', 'كاش'),
    ]
    
    PAYMENT_LOCATION_CHOICES = [
        ('in_person', 'حضوري'),
        ('remote', 'عن بعد'),
    ]
    
    # البيانات الأساسية
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    date = models.DateField(verbose_name='التاريخ')
    
    # نوع الإيراد
    income_type = models.CharField(max_length=15, choices=INCOME_TYPE_CHOICES, verbose_name='نوع الإيراد')
    
    # بيانات المبلغ
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ')

    # طريقة الدفع
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, verbose_name='طريقة الدفع')
    payment_location = models.CharField(max_length=10, choices=PAYMENT_LOCATION_CHOICES, default='in_person', verbose_name='مكان الدفع')
    
    # بيانات التحويل البنكي
    bank_account_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الحساب البنكي')
    
    # الموظف الذي حصل المبلغ
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='حصل بواسطة')
    
    # الدورة المرتبطة
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الدورة/الدبلومة')
    
    # بيانات إضافية (للتسجيل بأسلوب Excel)
    party_name = models.CharField(max_length=200, blank=True, verbose_name='الاسم / الجهة')
    id_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الهوية / الملف')
    collector_name = models.CharField(max_length=100, blank=True, verbose_name='اسم المحصل')
    transaction_number = models.CharField(max_length=50, blank=True, verbose_name='رقم العملية / الإيصال')
    
    # ملاحظات
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'إيراد'
        verbose_name_plural = 'الإيرادات'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        name = self.party_name or 'غير محدد'
        return f"{name} - {self.amount:,.2f} ({self.get_income_type_display()})"




class Expense(models.Model):
    EXPENSE_CATEGORY_CHOICES = [
        ('salaries', 'رواتب'),
        ('rent', 'إيجار'),
        ('utilities', 'مرافق (كهرباء، مياه، إنترنت)'),
        ('supplies', 'مستلزمات'),
        ('marketing', 'تسويق'),
        ('maintenance', 'صيانة'),
        ('bank', 'البنك (مصروفات ورسوم بنكية دورية)'),
        ('hospitality', 'ضيافة'),
        ('office_supplies', 'أدوات مكتبية'),
        ('transportation', 'انتقالات (حجز تذاكر)'),
        ('government', 'مصروفات حكومية'),
        ('fuel', 'محروقات (بنزين)'),
        ('car_maintenance', 'صيانة سيارات'),
        ('general_admin', 'مصروفات عمومية وإدارية'),
        ('other', 'أخرى'),
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    date = models.DateField(verbose_name='التاريخ')
    
    # بيانات المصروف
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORY_CHOICES, verbose_name='الفئة')
    description = models.CharField(max_length=200, verbose_name='الوصف')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ')
    
    # من قام بالصرف
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='تم الصرف بواسطة')
    
    # إيصال أو فاتورة
    receipt_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الإيصال/الفاتورة')
    receipt_image = models.ImageField(upload_to='receipts/%Y/%m/', blank=True, verbose_name='صورة الإيصال')
    
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'مصروف'
        verbose_name_plural = 'المصروفات'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.amount:,.2f}"


class DailySummary(models.Model):
    """ملخص يومي لكل فرع"""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    date = models.DateField(verbose_name='التاريخ')
    
    # الإيرادات
    total_registration_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إيرادات التسجيل')
    total_installment_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إيرادات التحصيل')
    total_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إجمالي الإيرادات')
    
    # المصروفات
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='إجمالي المصروفات')
    
    # الصافي
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='الصافي')
    
    # الأهداف
    daily_target = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='الهدف اليومي')
    achievement_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة الإنجاز %')
    
    # الإحصائيات
    new_registrations_count = models.PositiveIntegerField(default=0, verbose_name='عدد التسجيلات الجديدة')
    installments_collected_count = models.PositiveIntegerField(default=0, verbose_name='عدد الأقساط المحصلة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'ملخص يومي'
        verbose_name_plural = 'الملخصات اليومية'
        ordering = ['-date']
        unique_together = ['branch', 'date']
    
    def __str__(self):
        return f"{self.branch.name} - {self.date} - صافي: {self.net_amount:,.2f}"
    
    def calculate_summary(self):
        """حساب الملخص اليومي"""
        # حساب إيرادات التسجيل
        self.total_registration_income = Income.objects.filter(
            branch=self.branch,
            date=self.date,
            income_type='registration'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # حساب إيرادات التحصيل
        self.total_installment_income = Income.objects.filter(
            branch=self.branch,
            date=self.date,
            income_type='installment'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # إجمالي الإيرادات
        self.total_income = self.total_registration_income + self.total_installment_income
        
        # حساب المصروفات
        self.total_expenses = Expense.objects.filter(
            branch=self.branch,
            date=self.date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # الصافي
        self.net_amount = self.total_income - self.total_expenses
        
        # عدد التسجيلات الجديدة
        self.new_registrations_count = Income.objects.filter(
            branch=self.branch,
            date=self.date,
            income_type='registration'
        ).count()
        
        # عدد الأقساط المحصلة
        self.installments_collected_count = Income.objects.filter(
            branch=self.branch,
            date=self.date,
            income_type='installment'
        ).count()
        
        # نسبة الإنجاز
        if self.daily_target > 0:
            self.achievement_percentage = (self.total_income / self.daily_target) * 100
        
        self.save()
