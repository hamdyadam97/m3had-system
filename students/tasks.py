#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery tasks for the students app.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_installment_reminders_task(self):
    """
    Task to send installment reminders automatically.
    This task should be scheduled to run daily (e.g., at 9:00 AM).
    """
    try:
        from .services.notification_service import NotificationService
        
        logger.info("Starting automatic installment reminders...")
        count = NotificationService.process_reminders()
        logger.info(f"Successfully sent {count} reminders")
        
        return {
            'status': 'success',
            'reminders_sent': count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to send reminders: {exc}")
        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_payment_receipt_task(self, student_id, income_id, payment_data_dict):
    """
    Task to send payment receipt email to student asynchronously.
    """
    try:
        from .models import Student
        from transactions.models import Income
        from accounts.notifications import send_payment_receipt_to_student
        
        student = Student.objects.get(id=student_id)
        income = Income.objects.get(id=income_id)
        
        # Convert dict back to proper format
        from decimal import Decimal
        payment_data = {
            **payment_data_dict,
            'amount': Decimal(str(payment_data_dict.get('amount', 0))),
            'total_price': Decimal(str(payment_data_dict.get('total_price', 0))),
            'total_paid': Decimal(str(payment_data_dict.get('total_paid', 0))),
            'remaining': Decimal(str(payment_data_dict.get('remaining', 0))),
        }
        
        success = send_payment_receipt_to_student(student, income, payment_data)
        
        if success:
            logger.info(f"Payment receipt sent to {student.email}")
            return {'status': 'success', 'student': student.full_name}
        else:
            logger.warning(f"Failed to send receipt to {student.email}")
            return {'status': 'failed', 'student': student.full_name}
            
    except Exception as exc:
        logger.error(f"Error sending payment receipt: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def test_celery_task():
    """Simple test task."""
    logger.info("Celery is working! Test task executed successfully.")
    return "Test task completed!"
