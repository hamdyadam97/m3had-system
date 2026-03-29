#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إرسال تذكيرات الأقساط للطلاب
تشغيل: python manage.py send_installment_reminders
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from accounts.notifications import (
    send_installment_reminder,
    check_and_send_installment_reminders
)
from students.models import Student
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'إرسال تذكيرات الأقساط للطلاب (اليوم، غداً، بعد 3 أيام)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='عدد الأيام للفحص (افتراضي: 3)',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='وضع الاختبار - عرض فقط بدون إرسال',
        )

    def handle(self, *args, **options):
        days = options['days']
        test_mode = options['test']
        
        self.stdout.write(self.style.NOTICE(
            f'جاري فحص الأقساط المستحقة خلال {days} أيام...'
        ))
        
        today = date.today()
        reminder_days = [0, 1, 3]  # اليوم، غداً، بعد 3 أيام
        
        students = Student.objects.filter(
            payment_method='installment',
            is_active=True
        )
        
        total_sent = 0
        total_skipped = 0
        
        for student in students:
            try:
                info = student.get_next_installment_info()
                
                if not info:
                    continue
                
                days_until = info.get('days_until', -1)
                
                if days_until in reminder_days and student.phone:
                    if test_mode:
                        self.stdout.write(self.style.WARNING(
                            f'[TEST] {student.full_name} - '
                            f'قسط {info["installment_number"]} - '
                            f'مستحق: {info["due_date"]} - '
                            f'بعد {days_until} أيام'
                        ))
                        total_sent += 1
                    else:
                        success = send_installment_reminder(student, info)
                        if success:
                            total_sent += 1
                            self.stdout.write(self.style.SUCCESS(
                                f'✓ تم إرسال التذكير لـ {student.full_name}'
                            ))
                        else:
                            total_skipped += 1
                            self.stderr.write(self.style.ERROR(
                                f'✗ فشل إرسال التذكير لـ {student.full_name}'
                            ))
                            
            except Exception as e:
                logger.error(f"Error processing student {student}: {e}")
                self.stderr.write(self.style.ERROR(
                    f'خطأ في معالجة {student.full_name}: {e}'
                ))
        
        mode_text = "[وضع الاختبار] " if test_mode else ""
        self.stdout.write(self.style.SUCCESS(
            f'\n{mode_text}تم إرسال {total_sent} تذكير'
        ))
