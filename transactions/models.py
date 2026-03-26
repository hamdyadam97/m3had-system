from django.db import models
from accounts.models import User
from branches.models import Branch
from courses.models import Course
from students.models import Student


class Income(models.Model):
    INCOME_TYPE_CHOICES = [
        ('registration', 'تسجيل جديد'),
        ('installment', 'تحصيل قسط'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mada', 'مدى'),
        ('visa', 'فيزا'),
        ('bank_transfer', 'تحويل بنكي'),
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
    
    # بيانات الطالب
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='الطالب')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='الدورة/الدبلومة')


    # بيانات المبلغ
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ')
    installment = models.ForeignKey(
        'students.Installment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='القسط المرتبط'
    )

    # طريقة الدفع
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, verbose_name='طريقة الدفع')
    payment_location = models.CharField(max_length=10, choices=PAYMENT_LOCATION_CHOICES, verbose_name='مكان الدفع')
    
    # بيانات التحويل البنكي
    bank_account_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الحساب البنكي')
    
    # الموظف الذي حصل المبلغ
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='حصل بواسطة')
    
    # ملاحظات
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    enrollment = models.ForeignKey(
        'students.Enrollment',  # assuming Enrollment is in students app
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='payments',
        verbose_name='التسجيل'
    )

    def save(self, *args, **kwargs):
        # تعيين الفرع والدورة من الطالب
        if not self.branch_id and self.student_id:
            self.branch = self.student.branch
        if not self.course_id and self.student_id:
            self.course = self.student.course

        # ✅ ننشئ أو نجيب الـ Enrollment قبل الحفظ
        if self.student_id and self.course_id:
            from students.models import Enrollment  # import هنا عشان avoid circular import

            self.enrollment, created = Enrollment.objects.get_or_create(
                student=self.student,
                course=self.course,
                defaults={
                    'branch': self.branch,
                    'total_price': self.student.total_price,
                    'payment_method': self.student.payment_method,
                    'installment_count': self.student.installment_count,
                    'installment_amount': self.student.installment_amount,
                    'status': 'active',
                }
            )

        super().save(*args, **kwargs)

        # ✅ نحدث الـ Enrollment بعد الحفظ
        if self.enrollment:
            self._update_enrollment()

    def _update_enrollment(self):
        """تحديث بيانات الـ Enrollment بعد الدفع"""
        from django.db.models import Sum

        # حساب إجمالي المدفوع للـ Enrollment ده
        total_paid = Income.objects.filter(
            enrollment=self.enrollment
        ).aggregate(total=Sum('amount'))['total'] or 0

        enrollment = self.enrollment

        # تحديث عدد الأقساط المدفوعة
        if enrollment.payment_method == 'installment' and enrollment.installment_amount > 0:
            enrollment.paid_installments = min(
                int(total_paid / enrollment.installment_amount),
                enrollment.installment_count
            )

        # تفعيل الاشتراك لو أول دفعة
        if enrollment.status == 'pending' and total_paid > 0:
            enrollment.status = 'active'

        enrollment.save()
    class Meta:
        verbose_name = 'إيراد'
        verbose_name_plural = 'الإيرادات'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.student.full_name} - {self.amount:,.2f} ({self.get_income_type_display()})"

    # داخل كلاس Income في transactions/models.py

    def _link_to_installment(self):
        """ربط الإيراد بأول قسط مش مدفوع"""
        try:
            plan = self.student.installment_plan
            # ندور على أول قسط مش مدفوع بنفس المبلغ أو أقل
            installment = plan.installments.filter(is_paid=False).first()
            if installment:
                self.installment = installment
        except:
            pass




class Expense(models.Model):
    EXPENSE_CATEGORY_CHOICES = [
        ('salaries', 'رواتب'),
        ('rent', 'إيجار'),
        ('utilities', 'مرافق (كهرباء، مياه، إنترنت)'),
        ('supplies', 'مستلزمات'),
        ('marketing', 'تسويق'),
        ('maintenance', 'صيانة'),
        ('other', 'أخرى'),
    ]
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    date = models.DateField(verbose_name='التاريخ')
    
    # بيانات المصروف
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORY_CHOICES, verbose_name='الفئة')
    description = models.CharField(max_length=200, verbose_name='الوصف')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المبلغ')
    
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
