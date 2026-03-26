from django.db import models
from django.utils import timezone
from branches.models import Branch
from courses.models import Course

# students/models.py

from django.db import models
from django.utils import timezone
from branches.models import Branch
from courses.models import Course


class Enrollment(models.Model):
    """تسجيل طالب في دورة - يسمح للطالب بالتسجيل في دورات متعددة متتالية"""

    STATUS_CHOICES = [
        ('active', 'نشط'),  # الدورة شغالة حالياً
        ('completed', 'مكتمل'),  # الطالب خلص الدورة
        ('withdrawn', 'منسحب'),  # الطالب انسحب من الدورة
        ('suspended', 'معلق'),  # الدورة موقفة مؤقتاً
    ]

    ENROLLMENT_TYPE_CHOICES = [
        ('new', 'تسجيل جديد'),
        ('improvement', 'تقوية'),  # نفس الدورة للتقوية
        ('repeat', 'إعادة'),  # إعادة الدورة
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='enrollments', verbose_name='الطالب')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='الدورة/الدبلومة')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')

    # نوع التسجيل
    enrollment_type = models.CharField(max_length=15, choices=ENROLLMENT_TYPE_CHOICES, default='new',
                                       verbose_name='نوع التسجيل')

    # حالة التسجيل
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active', verbose_name='حالة التسجيل')

    # بيانات الدفع
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر الإجمالي')
    payment_method = models.CharField(max_length=15, choices=[('full', 'دفعة واحدة'), ('installment', 'قسط')],
                                      verbose_name='طريقة الدفع')

    # بيانات الأقساط
    installment_count = models.PositiveIntegerField(default=1, verbose_name='عدد الأقساط')
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='قيمة القسط')
    first_installment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ أول قسط')

    # التواريخ
    enrollment_date = models.DateField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    start_date = models.DateField(null=True, blank=True, verbose_name='تاريخ البدء')
    end_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الانتهاء')

    # إذا كان انسحاب
    withdrawal_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الانسحاب')
    withdrawal_reason = models.TextField(blank=True, verbose_name='سبب الانسحاب')

    # ملاحظات
    notes = models.TextField(blank=True, verbose_name='ملاحظات')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name = 'تسجيل دورة'
        verbose_name_plural = 'تسجيلات الدورات'
        ordering = ['-enrollment_date']
        # الطالب مينفعش يكون مسجل في نفس الدورة مرتين بنفس الوقت (لو حالته نشطة)
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course', 'status'],
                condition=models.Q(status='active'),
                name='unique_active_enrollment'
            )
        ]

    def __str__(self):
        status_display = dict(self.STATUS_CHOICES).get(self.status, self.status)
        return f"{self.student.full_name} - {self.course.name} ({status_display})"

    def save(self, *args, **kwargs):
        # إذا كان التسجيل جديد ونشط، نحدث الطالب
        is_new = self.pk is None

        super().save(*args, **kwargs)

        # ✅ تحديث بيانات الطالب في جدول Student بالتسجيل الحالي
        if self.status == 'active':
            self._update_student_current_course()

    def _update_student_current_course(self):
        """تحديث جدول Student ببيانات الدورة الحالية (التسجيل النشط)"""
        student = self.student

        # تحديث الحقول الأساسية
        student.course = self.course
        student.branch = self.branch
        student.total_price = self.total_price
        student.payment_method = self.payment_method
        student.installment_count = self.installment_count
        student.installment_amount = self.installment_amount

        # حفظ التغييرات
        student.save(update_fields=[
            'course', 'branch', 'total_price',
            'payment_method', 'installment_count', 'installment_amount'
        ])

    def is_active(self):
        """هل التسجيل نشط؟"""
        return self.status == 'active'

    def can_complete(self):
        """يمكن إكمال الدورة؟"""
        return self.status == 'active'

    def can_withdraw(self):
        """يمكن الانسحاب؟"""
        return self.status == 'active'

    def mark_completed(self):
        """تحديد الدورة كمكتملة"""
        if self.can_complete():
            self.status = 'completed'
            self.end_date = timezone.now().date()
            self.save()

            # ✅ عند إكمال الدورة، نبحث عن تسجيل نشط آخر ونحدث الطالب به
            self._activate_next_enrollment()
            return True
        return False

    def mark_withdrawn(self, reason=''):
        """تحديد الانسحاب من الدورة"""
        if self.can_withdraw():
            self.status = 'withdrawn'
            self.withdrawal_date = timezone.now().date()
            self.withdrawal_reason = reason
            self.save()

            # ✅ عند الانسحاب، نبحث عن تسجيل نشط آخر
            self._activate_next_enrollment()
            return True
        return False

    def _activate_next_enrollment(self):
        """تفعيل التسجيل التالي (الأحدث) وتحديث بيانات الطالب"""
        # البحث عن آخر تسجيل غير مكتمل وغير منسحب
        next_enrollment = self.student.enrollments.exclude(
            status__in=['completed', 'withdrawn']
        ).order_by('-enrollment_date').first()

        if next_enrollment:
            # تفعيله كـ active
            next_enrollment.status = 'active'
            next_enrollment.save()
        else:
            # لا يوجد تسجيل آخر - يمكن مسح بيانات الطالب أو تركها كما هي
            pass

    def get_total_paid(self):
        """إجمالي المدفوعات لهذا التسجيل"""
        from transactions.models import Income
        return Income.objects.filter(
            enrollment=self
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def get_remaining_amount(self):
        """المبلغ المتبقي لهذا التسجيل"""
        return self.total_price - self.get_total_paid()

    def is_fully_paid(self):
        """هل تم الدفع كاملاً لهذا التسجيل؟"""
        return self.get_remaining_amount() <= 0

    def get_status_color(self):
        """لون الحالة للعرض"""
        color_map = {
            'active': 'success',
            'completed': 'primary',
            'withdrawn': 'secondary',
            'suspended': 'warning',
        }
        return color_map.get(self.status, 'secondary')

    def has_overdue_installments(self):
        """هل يوجد أقساط متأخرة؟"""
        # يمكن ربطها بـ InstallmentPlan إذا كان هناك نظام أقساط للتسجيل
        return False  # يحتاج تخصيص حسب نظام الأقساط

    def get_overdue_days(self):
        """عدد أيام التأخر"""
        return 0  # يحتوب تخصيص