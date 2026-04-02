import requests
import json
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from ..models import NotificationSettings, NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    """خدمة إرسال الإشعارات عبر البريد وواتساب"""

    @staticmethod
    def get_settings():
        """الحصول على إعدادات الإشعارات"""
        return NotificationSettings.get_settings()

    @classmethod
    def send_reminder(cls, installment, reminder_type):
        """
        إرسال تذكير للقسط
        reminder_type: '2days', '1day', 'due', 'overdue'
        """
        settings = cls.get_settings()
        student = installment.plan.student

        # إعداد بيانات القالب
        template_data = {
            'student_name': student.full_name,
            'installment_number': installment.installment_number,
            'amount': installment.amount,
            'due_date': installment.due_date.strftime('%Y-%m-%d'),
            'overdue_days': installment.days_overdue(),
            'contact_phone': settings.contact_phone,
        }

        # اختيار قالب الرسالة
        if reminder_type == '2days':
            template = settings.reminder_2days_template
        elif reminder_type == '1day':
            template = settings.reminder_1day_template
        elif reminder_type == 'due':
            template = settings.reminder_due_template
        elif reminder_type == 'overdue':
            template = settings.overdue_template
        else:
            return False

        message = template.format(**template_data)

        results = {'email': False, 'whatsapp': False}

        # إرسال عبر البريد
        if settings.email_enabled and student.email:
            results['email'] = cls._send_email(
                to_email=student.email,
                subject=f'تذكير بقسط مستحق - {student.full_name}',
                message=message,
                installment=installment,
                reminder_type=reminder_type
            )

        # إرسال عبر واتساب
        if settings.whatsapp_enabled and student.phone:
            results['whatsapp'] = cls._send_whatsapp(
                phone=student.phone,
                message=message,
                installment=installment,
                reminder_type=reminder_type
            )

        return results['email'] or results['whatsapp']

    @classmethod
    def _send_email(cls, to_email, subject, message, installment, reminder_type):
        """إرسال بريد إلكتروني"""
        settings_obj = cls.get_settings()

        try:
            # إنشاء سجل الإشعار
            log = NotificationLog.objects.create(
                student=installment.plan.student,
                installment=installment,
                notification_type='email',
                notification_reason=f'{reminder_type}_before' if reminder_type in ['2days', '1day'] else reminder_type,
                recipient=to_email,
                subject=subject,
                message=message,
                status='pending'
            )

            # إعدادات Django للبريد
            from django.core.mail import get_connection

            connection = get_connection(
                host=settings_obj.email_host or settings.EMAIL_HOST,
                port=settings_obj.email_port or settings.EMAIL_PORT,
                username=settings_obj.email_host_user or settings.EMAIL_HOST_USER,
                password=settings_obj.email_host_password or settings.EMAIL_HOST_PASSWORD,
                use_tls=settings_obj.email_use_tls,
            )

            from_email = settings_obj.email_from_address or settings.DEFAULT_FROM_EMAIL

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[to_email],
                connection=connection,
                fail_silently=False,
            )

            # تحديث السجل
            log.status = 'sent'
            log.save()

            # تحديث حالة القسط
            cls._update_installment_reminder_status(installment, reminder_type)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            if 'log' in locals():
                log.status = 'failed'
                log.error_message = str(e)
                log.save()
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    @classmethod
    def _send_whatsapp(cls, phone, message, installment, reminder_type):
        """إرسال رسالة واتساب"""
        settings_obj = cls.get_settings()

        if not settings_obj.whatsapp_api_key or not settings_obj.whatsapp_instance_id:
            logger.warning("WhatsApp API not configured")
            return False

        try:
            # إنشاء سجل الإشعار
            log = NotificationLog.objects.create(
                student=installment.plan.student,
                installment=installment,
                notification_type='whatsapp',
                notification_reason=f'{reminder_type}_before' if reminder_type in ['2days', '1day'] else reminder_type,
                recipient=phone,
                message=message,
                status='pending'
            )

            # تنسيق رقم الهاتف
            formatted_phone = cls._format_phone_number(phone)

            # إرسال عبر API
            api_url = settings_obj.whatsapp_api_url.format(
                instance_id=settings_obj.whatsapp_instance_id
            )

            payload = {
                'token': settings_obj.whatsapp_api_key,
                'to': formatted_phone,
                'body': message,
            }

            response = requests.post(api_url, data=payload, timeout=30)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('sent'):
                log.status = 'sent'
                log.response_data = json.dumps(response_data)
                log.save()

                # تحديث حالة القسط
                cls._update_installment_reminder_status(installment, reminder_type)

                logger.info(f"WhatsApp message sent successfully to {formatted_phone}")
                return True
            else:
                log.status = 'failed'
                log.error_message = response_data.get('message', 'Unknown error')
                log.response_data = json.dumps(response_data)
                log.save()
                logger.error(f"Failed to send WhatsApp message: {response_data}")
                return False

        except Exception as e:
            if 'log' in locals():
                log.status = 'failed'
                log.error_message = str(e)
                log.save()
            logger.error(f"Failed to send WhatsApp message to {phone}: {str(e)}")
            return False

    @classmethod
    def _format_phone_number(cls, phone):
        """تنسيق رقم الهاتف للواتساب"""
        # إزالة المسافات والرموز
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')

        # إضافة كود الدولة إذا لم يكن موجوداً
        if phone.startswith('0'):
            phone = '966' + phone[1:]  # افتراض السعودية
        elif not phone.startswith('966'):
            phone = '966' + phone

        return phone

    @classmethod
    def _update_installment_reminder_status(cls, installment, reminder_type):
        """تحديث حالة الإشعار للقسط"""
        if reminder_type == '2days':
            installment.reminder_sent_2days = True
        elif reminder_type == '1day':
            installment.reminder_sent_1day = True
        elif reminder_type == 'due':
            installment.reminder_sent_due = True
        elif reminder_type == 'overdue':
            installment.overdue_notice_sent = True

        installment.save(update_fields=[
            'reminder_sent_2days', 'reminder_sent_1day',
            'reminder_sent_due', 'overdue_notice_sent'
        ])

    @classmethod
    def process_reminders(cls):
        """
        معالجة جميع التذكيرات المستحقة
        تُستدعى هذه الدالة بشكل دوري (مثلاً كل ساعة)
        """
        from ..installment_models import Installment

        settings = cls.get_settings()
        today = timezone.now().date()

        sent_count = 0

        # 1. تذكير قبل يومين
        if settings.reminder_2days_before:
            target_date = today + timezone.timedelta(days=2)
            installments = Installment.objects.filter(
                is_paid=False,
                due_date=target_date,
                reminder_sent_2days=False
            )

            for installment in installments:
                if cls.send_reminder(installment, '2days'):
                    sent_count += 1

        # 2. تذكير قبل يوم
        if settings.reminder_1day_before:
            target_date = today + timezone.timedelta(days=1)
            installments = Installment.objects.filter(
                is_paid=False,
                due_date=target_date,
                reminder_sent_1day=False
            )

            for installment in installments:
                if cls.send_reminder(installment, '1day'):
                    sent_count += 1

        # 3. تذكير يوم الاستحقاق
        if settings.reminder_on_due_date:
            installments = Installment.objects.filter(
                is_paid=False,
                due_date=today,
                reminder_sent_due=False
            )

            for installment in installments:
                if cls.send_reminder(installment, 'due'):
                    sent_count += 1

        # 4. إشعار التأخر
        if settings.send_overdue_notice:
            installments = Installment.objects.filter(
                is_paid=False,
                due_date__lt=today,
                overdue_notice_sent=False
            )

            for installment in installments:
                if cls.send_reminder(installment, 'overdue'):
                    sent_count += 1

        logger.info(f"Processed {sent_count} reminders")
        return sent_count