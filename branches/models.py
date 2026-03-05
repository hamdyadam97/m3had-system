from django.db import models
from django.core.validators import MinValueValidator
from datetime import date


class Branch(models.Model):
    name = models.CharField(max_length=100, verbose_name='اسم الفرع')
    code = models.CharField(max_length=10, unique=True, verbose_name='كود الفرع')
    address = models.TextField(blank=True, verbose_name='العنوان')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    # هذا السطر هو المسؤول عن ظهور الاسم بدلاً من Branch object (1)
    def __str__(self):
        return self.name

    def get_current_month_target(self):
        """جلب مبلغ الهدف للشهر الحالي"""
        today = date.today()
        target_obj = self.targets.filter(year=today.year, month=today.month).first()
        return float(target_obj.amount) if target_obj else 0.0

    @property
    def get_daily_target(self):
        """يحسب الهدف اليومي (الشهري ÷ 30)"""
        monthly_target = self.get_current_month_target()
        if monthly_target > 0:
            return monthly_target / 30
        return 0.0


class BranchTarget(models.Model):
    MONTH_CHOICES = [
        (1, 'يناير'), (2, 'فبراير'), (3, 'مارس'), (4, 'أبريل'),
        (5, 'مايو'), (6, 'يونيو'), (7, 'يوليو'), (8, 'أغسطس'),
        (9, 'سبتمبر'), (10, 'أكتوبر'), (11, 'نوفمبر'), (12, 'ديسمبر'),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='targets', verbose_name='الفرع')
    year = models.PositiveIntegerField(default=date.today().year, verbose_name='السنة')
    month = models.PositiveIntegerField(choices=MONTH_CHOICES, verbose_name='الشهر')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='المبلغ المستهدف',
                                 validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = 'هدف الفرع'
        verbose_name_plural = 'أهداف الفروع'
        unique_together = ['branch', 'year', 'month']  # يمنع تكرار الهدف لنفس الفرع في نفس الشهر

    def __str__(self):
        return f"هدف {self.branch.name} - {self.month}/{self.year}"

