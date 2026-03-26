from django.db import models
from branches.models import Branch
from courses.models import Course
from django.utils import timezone
from dateutil.relativedelta import relativedelta

class Student(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('full', 'دفعة واحدة'),
        ('installment', 'قسط'),
    ]


    full_name = models.CharField(max_length=200, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    national_id = models.CharField(max_length=20, blank=True, verbose_name='رقم البطاقة')
    address = models.TextField(blank=True, verbose_name='العنوان')
    
    # بيانات التسجيل
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, verbose_name='الفرع')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='الدورة/الدبلوما')
    registration_date = models.DateField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    
    # بيانات الدفع
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر الإجمالي')
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, verbose_name='طريقة الدفع')

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



    def get_payment_schedule(self):
        """
        جدولة الدفع المتوقعة للطالب
        ترجع قائمة بالأقساط: [رقم القسط, التاريخ, المبلغ, حالة الدفع]
        """
        if self.payment_method != 'installment':
            # دفعة كاملة - قسط واحد بس
            return [{
                'number': 1,
                'due_date': self.registration_date,
                'amount': self.total_price,
                'is_paid': self.is_fully_paid(),
                'status': 'paid' if self.is_fully_paid() else 'due'
            }]

        # نظام الأقساط
        schedule = []
        first_date = self.first_installment_date or self.registration_date

        for i in range(self.installment_count):
            due_date = first_date + relativedelta(months=i)

            # معرفة حالة القسط
            is_paid = self.paid_installments > i

            schedule.append({
                'number': i + 1,
                'due_date': due_date,
                'amount': self.installment_amount,
                'is_paid': is_paid,
                'status': 'paid' if is_paid else self._get_installment_status(due_date)
            })

        return schedule

    def _get_installment_status(self, due_date):
        """حالة القسط حسب التاريخ"""
        today = timezone.now().date()

        if due_date < today:
            return 'overdue'  # متأخر
        elif due_date == today:
            return 'due_today'  # مستحق اليوم
        elif (due_date - today).days <= 5:
            return 'due_soon'  # مستحق قريباً
        else:
            return 'upcoming'  # قادم

    def get_current_installment(self):
        """القسط الحالي اللي المفروض يتدفع"""
        schedule = self.get_payment_schedule()

        for inst in schedule:
            if not inst['is_paid']:
                return inst

        return None  # كل الأقساط مدفوعة

    def get_next_installment_info(self):
        """معلومات القسط القادم"""
        current = self.get_current_installment()

        if not current:
            return None

        today = timezone.now().date()
        days_until = (current['due_date'] - today).days

        return {
            'installment_number': current['number'],
            'due_date': current['due_date'],
            'amount': current['amount'],
            'days_until': days_until,
            'status': current['status'],
            'can_pay_early': days_until > 0,  # يقدر يدفع قبل المعاد
            'is_overdue': current['status'] == 'overdue'
        }

    def can_pay_installment_now(self, early_days_allowed=5):
        """
        هل يمكن دفع قسط الآن؟
        early_days_allowed: كم يوم قبل المعاد نسمح بالدفع المبكر
        """
        info = self.get_next_installment_info()

        if not info:
            return False, "لا يوجد أقساط مستحقة"

        # لو متأخر أو مستحق اليوم → يقدر يدفع
        if info['status'] in ['overdue', 'due_today']:
            return True, "قسط مستحق"

        # لو قريب → يقدر يدفع مبكر
        if info['status'] == 'due_soon':
            return True, f"قسط مستحق قريباً (بعد {info['days_until']} يوم)"

        # لو بعيد → مينفعش (إلا لو عايز تسديد كامل)
        if info['status'] == 'upcoming':
            return False, f"القسط القادم بعد {info['days_until']} يوم"

        return False, "غير معروف"

    def get_payable_amounts(self):
        """
        المبالغ المتاح دفعها الآن
        """
        info = self.get_next_installment_info()
        remaining = self.get_remaining_amount()

        if not info:
            return {
                'can_pay': False,
                'reason': 'لا يوجد رصيد مستحق'
            }

        amounts = {
            'can_pay': True,
            'current_installment': {
                'number': info['installment_number'],
                'amount': info['amount'],
                'due_date': info['due_date'].strftime('%Y-%m-%d'),
                'status': info['status'],
                'is_overdue': info['is_overdue']
            },
            'remaining_total': remaining,
            'options': []
        }

        # الخيارات المتاحة:

        # 1. دفع القسط الحالي فقط
        amounts['options'].append({
            'type': 'current',
            'label': f'قسط {info["installment_number"]}',
            'amount': info['amount'],
            'description': f'دفع قسط {info["installment_number"]} المستحق'
        })

        # 2. دفع القسط + القسط الجاي (لو فيه)
        next_next = None
        schedule = self.get_payment_schedule()
        for inst in schedule:
            if inst['number'] == info['installment_number'] + 1:
                next_next = inst
                break

        if next_next and not next_next['is_paid']:
            double_amount = info['amount'] + next_next['amount']
            amounts['options'].append({
                'type': 'double',
                'label': f'قسطين معاً',
                'amount': double_amount,
                'description': f'قسط {info["installment_number"]} + قسط {next_next["number"]}'
            })

        # 3. تسديد كامل
        if remaining > info['amount']:
            amounts['options'].append({
                'type': 'full',
                'label': 'تسديد كامل',
                'amount': remaining,
                'description': f'سداد باقي المبلغ كله ({remaining:,.0f} ر.س)'
            })

        # 4. مبلغ مخصص (أي رقم بين القسط والمتبقي)
        amounts['options'].append({
            'type': 'custom',
            'label': 'مبلغ مخصص',
            'amount': None,  # المستخدم يدخله
            'min': info['amount'],
            'max': remaining,
            'description': f'أي مبلغ بين {info["amount"]:,.0f} و {remaining:,.0f} ر.س'
        })

        return amounts

    def has_active_enrollment(self):
        """هل مسجل في دورة حالياً؟"""
        return self.enrollments.filter(status='active').exists() or self.get_total_paid() == 0

    def get_active_enrollment(self):
        try:
            # هنا فيه خطأ بسيط: ناديت self.has_active_enrollment كأنها متغير مش ميثود
            if self.has_active_enrollment():
                return self.enrollments.filter(status='active').first()
        except:
            return None
        return None  # لو الشرط ملم يتحقق بترجع None

    # داخل كلاس Student في models.py

    def can_enroll_in_new_course(self):
        """
        يمنع التسجيل في دورة جديدة في حالتين:
        1. لو فيه Enrollment حالة status='active' (دورة شغال فيها فعلياً).
        2. لو الطالب عنده حجز (course) بس لسه مدفعش تمنه (get_total_paid == 0).
        """
        # التأكد من عدم وجود دورة نشطة
        has_active = self.enrollments.filter(status='active').exists()
        if has_active:
            return False

        # المنع اللي أنت عايزه: لو الطالب لسه "جديد" ومسددش حتى القسط الأول للحجز الحالي
        if self.get_total_paid() <= 0:
            return False

        return True


    def get_course_history(self):
        """تاريخ الدورات (المكتملة والمنسحبة)"""
        return self.enrollments.filter(status__in=['completed', 'withdrawn']).order_by('-enrollment_date')

    def get_first_payment_amount(self):
        """مبلغ أول دفعة"""
        if self.payment_method == 'installment':
            return self.installment_amount  # أول قسط
        else:
            return self.total_price  # الدفعة الكاملة

    def get_remaining_after_first(self):
        """المتبقي بعد أول دفعة"""
        first_paid = self.get_total_paid_for_registration()
        if self.payment_method == 'installment':
            return self.total_price - self.installment_amount  # باقي الأقساط
        else:
            return 0  # كاش مفيش باقي
    
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
        if hasattr(self, 'installment_plan') and self.installment_plan:
            return self.installment_plan.has_overdue_installments()
        return False
    
    def get_overdue_days(self):
        """عدد أيام التأخر للأقساط المتأخرة"""
        if hasattr(self, 'installment_plan') and self.installment_plan:
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


    def get_total_paid(self):
        """إجمالي المدفوعات"""
        from transactions.models import Income
        return Income.objects.filter(student=self).aggregate(
            total=models.Sum('amount')
        )['total'] or 0

    def get_total_paid_for_registration(self):
        """إجمالي مدفوعات التسجيل فقط"""
        from transactions.models import Income
        return Income.objects.filter(
            student=self,
            income_type='registration'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def get_remaining_amount(self):
        """المبلغ المتبقي على الطالب"""
        total_paid = self.get_total_paid()
        return (self.total_price  or 0) - total_paid

    def is_new_registration(self):
        """هل الطالب جديد (ميسددش التسجيل كامل)"""
        reg_paid = self.get_total_paid_for_registration()

        # ✅ لو نظام أقساط → التسجيل = أول قسط
        if self.payment_method == 'installment':
            return reg_paid < self.installment_amount
        else:
            # ✅ لو كاش → التسجيل = الدفعة الكاملة
            return reg_paid < self.total_price

    def can_pay_installment(self):
        """هل يمكنه دفع قسط"""
        return self.get_remaining_amount() > 0 and not self.is_new_registration()

# استيراد النماذج الإضافية
from .installment_models import InstallmentPlan, Installment
from .notification_models import NotificationSettings, NotificationLog
from .enrollment_models import Enrollment

# إضافة خاصية للنموذج للوصول السريع
Student.installment_plan = property(
    lambda self: InstallmentPlan.objects.filter(student=self).first()
)


# الحصول على جميع الدورات السابقة
Student.get_completed_courses = lambda self: self.enrollments.filter(status='completed')
Student.get_withdrawn_courses = lambda self: self.enrollments.filter(status='withdrawn')