from django.db import models
from django.conf import settings


class NotificationSettings(models.Model):
    """إعدادات الإشعارات والتذكيرات"""
    
    # إعدادات البريد الإلكتروني
    email_enabled = models.BooleanField(default=True, verbose_name='تفعيل إشعارات البريد')
    email_host = models.CharField(max_length=255, blank=True, verbose_name='خادم البريد (SMTP)')
    email_port = models.PositiveIntegerField(default=587, verbose_name='منفذ البريد')
    email_host_user = models.CharField(max_length=255, blank=True, verbose_name='اسم مستخدم البريد')
    email_host_password = models.CharField(max_length=255, blank=True, verbose_name='كلمة مرور البريد')
    email_use_tls = models.BooleanField(default=True, verbose_name='استخدام TLS')
    email_from_address = models.EmailField(blank=True, verbose_name='عنوان المرسل')
    
    # إعدادات واتساب
    whatsapp_enabled = models.BooleanField(default=True, verbose_name='تفعيل إشعارات واتساب')
    whatsapp_api_key = models.CharField(max_length=500, blank=True, verbose_name='مفتاح API واتساب')
    whatsapp_api_url = models.URLField(
        default='https://api.ultramsg.com/instance{instance_id}/messages/chat',
        blank=True,
        verbose_name='رابط API واتساب'
    )
    whatsapp_instance_id = models.CharField(max_length=50, blank=True, verbose_name='معرف Instance')
    
    # قوالب الرسائل
    reminder_2days_template = models.TextField(
        default='مرحباً {student_name}،\n\nنذكركم بأن القسط رقم {installment_number} بمبلغ {amount} ريال مستحق بعد يومين بتاريخ {due_date}.\n\nشكراً لاختياركم معهدنا.',
        verbose_name='قالب تذكير قبل يومين'
    )
    
    reminder_1day_template = models.TextField(
        default='مرحباً {student_name}،\n\nنذكركم بأن القسط رقم {installment_number} بمبلغ {amount} ريال مستحق غداً بتاريخ {due_date}.\n\nشكراً لاختياركم معهدنا.',
        verbose_name='قالب تذكير قبل يوم'
    )
    
    reminder_due_template = models.TextField(
        default='مرحباً {student_name}،\n\nنذكركم بأن القسط رقم {installment_number} بمبلغ {amount} ريال مستحق اليوم بتاريخ {due_date}.\n\nيرجى السداد في أقرب وقت ممكن.\n\nشكراً لكم.',
        verbose_name='قالب تذكير يوم الاستحقاق'
    )
    
    overdue_template = models.TextField(
        default='مرحباً {student_name}،\n\nنفيدكم بأن القسط رقم {installment_number} بمبلغ {amount} ريال قد تجاوز تاريخ الاستحقاق بتاريخ {due_date} ولم يتم السداد حتى الآن.\n\nعدد أيام التأخر: {overdue_days} يوم\n\nيرجى السداد فوراً لتجنب أي إجراءات إضافية.\n\nللاستفسار: {contact_phone}',
        verbose_name='قالب إشعار التأخر'
    )
    
    # الإعدادات العامة
    reminder_2days_before = models.BooleanField(default=True, verbose_name='إرسال تذكير قبل يومين')
    reminder_1day_before = models.BooleanField(default=True, verbose_name='إرسال تذكير قبل يوم')
    reminder_on_due_date = models.BooleanField(default=True, verbose_name='إرسال تذكير يوم الاستحقاق')
    send_overdue_notice = models.BooleanField(default=True, verbose_name='إرسال إشعار التأخر')
    
    contact_phone = models.CharField(max_length=20, default='', blank=True, verbose_name='رقم التواصل للاستفسار')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إعدادات الإشعارات'
        verbose_name_plural = 'إعدادات الإشعارات'
    
    def __str__(self):
        return 'إعدادات الإشعارات'
    
    @classmethod
    def get_settings(cls):
        """الحصول على الإعدادات أو إنشاء افتراضية"""
        settings_obj, created = cls.objects.get_or_create(pk=1)
        return settings_obj


class NotificationLog(models.Model):
    """سجل الإشعارات المرسلة"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('email', 'بريد إلكتروني'),
        ('whatsapp', 'واتساب'),
        ('sms', 'رسالة نصية'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'قيد الإرسال'),
        ('sent', 'تم الإرسال'),
        ('failed', 'فشل الإرسال'),
    ]
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='notifications', verbose_name='الطالب')
    installment = models.ForeignKey('Installment', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications', verbose_name='القسط')
    
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE_CHOICES, verbose_name='نوع الإشعار')
    notification_reason = models.CharField(max_length=50, verbose_name='سبب الإشعار')  # 2days_before, 1day_before, due, overdue
    
    recipient = models.CharField(max_length=255, verbose_name='المستلم')
    subject = models.CharField(max_length=255, blank=True, verbose_name='الموضوع')
    message = models.TextField(verbose_name='محتوى الرسالة')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    response_data = models.TextField(blank=True, verbose_name='بيانات الاستجابة')
    error_message = models.TextField(blank=True, verbose_name='رسالة الخطأ')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    
    class Meta:
        verbose_name = 'سجل إشعار'
        verbose_name_plural = 'سجل الإشعارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.student.full_name} - {self.get_notification_reason_display()}"
    
    def get_notification_reason_display(self):
        """نص سبب الإشعار"""
        reason_map = {
            '2days_before': 'قبل يومين',
            '1day_before': 'قبل يوم',
            'due': 'يوم الاستحقاق',
            'overdue': 'إشعار تأخر',
        }
        return reason_map.get(self.notification_reason, self.notification_reason)
