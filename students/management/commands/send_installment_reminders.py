"""
أمر إدارة لإرسال تذكيرات الأقساط
يُنفذ هذا الأمر بشكل دوري (مثلاً كل ساعة) عبر Cron Job
"""
from django.core.management.base import BaseCommand
from students.services.notification_service import NotificationService


class Command(BaseCommand):
    help = 'إرسال تذكيرات الأقساط المستحقة (يومين قبل، يوم قبل، يوم الاستحقاق، إشعار تأخر)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='عرض الأقساط المستحقة دون إرسال إشعارات',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('وضع العرض فقط - لن يتم إرسال أي إشعارات'))
            # عرض الأقساط المستحقة
            from django.utils import timezone
            from students.installment_models import Installment
            
            today = timezone.now().date()
            
            # قبل يومين
            target_date = today + timezone.timedelta(days=2)
            installments_2days = Installment.objects.filter(
                is_paid=False, due_date=target_date, reminder_sent_2days=False
            )
            self.stdout.write(f"\nتذكيرات قبل يومين ({target_date}): {installments_2days.count()}")
            for inst in installments_2days:
                self.stdout.write(f"  - {inst.plan.student.full_name}: القسط {inst.installment_number}")
            
            # قبل يوم
            target_date = today + timezone.timedelta(days=1)
            installments_1day = Installment.objects.filter(
                is_paid=False, due_date=target_date, reminder_sent_1day=False
            )
            self.stdout.write(f"\nتذكيرات قبل يوم ({target_date}): {installments_1day.count()}")
            for inst in installments_1day:
                self.stdout.write(f"  - {inst.plan.student.full_name}: القسط {inst.installment_number}")
            
            # يوم الاستحقاق
            installments_due = Installment.objects.filter(
                is_paid=False, due_date=today, reminder_sent_due=False
            )
            self.stdout.write(f"\nتذكيرات يوم الاستحقاق ({today}): {installments_due.count()}")
            for inst in installments_due:
                self.stdout.write(f"  - {inst.plan.student.full_name}: القسط {inst.installment_number}")
            
            # متأخرة
            overdue = Installment.objects.filter(
                is_paid=False, due_date__lt=today, overdue_notice_sent=False
            )
            self.stdout.write(f"\nأقساط متأخرة: {overdue.count()}")
            for inst in overdue:
                self.stdout.write(f"  - {inst.plan.student.full_name}: القسط {inst.installment_number} ({inst.days_overdue()} يوم تأخر)")
            
        else:
            self.stdout.write('جاري إرسال التذكيرات...')
            count = NotificationService.process_reminders()
            self.stdout.write(self.style.SUCCESS(f'تم إرسال {count} تذكير بنجاح'))
