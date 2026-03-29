#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إرسال التقارير اليومية للمديرين والمديرين الإقليميين والأدمن
تشغيل: python manage.py send_daily_reports
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum, Count
from accounts.models import User
from accounts.notifications import (
    send_daily_report_to_branch_manager,
    send_daily_report_to_regional_manager,
    send_daily_summary_to_manager_whatsapp,
    send_daily_report_to_admins
)
from branches.models import Branch
from transactions.models import Income, Expense
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'إرسال التقارير اليومية للمديرين والمديرين الإقليميين والأدمن'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='وضع الاختبار - إرسال للمستخدم الحالي فقط',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='تاريخ معين (YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        # تحديد التاريخ
        if options['date']:
            try:
                report_date = date.fromisoformat(options['date'])
            except ValueError:
                self.stderr.write(self.style.ERROR('تاريخ غير صالح. استخدم YYYY-MM-DD'))
                return
        else:
            report_date = date.today()

        self.stdout.write(self.style.NOTICE(f'جاري إرسال تقارير يوم: {report_date}'))
        
        total_sent_emails = 0
        total_sent_whatsapp = 0

        # ========== 1. إرسال تقارير لمديري الفروع ==========
        self.stdout.write(self.style.NOTICE('\n📧 جاري إرسال تقارير مديري الفروع...'))
        
        managers = User.objects.filter(
            user_type='branch_manager',
            is_active=True,
            branch__isnull=False
        )

        for manager in managers:
            try:
                branch = manager.branch
                
                # حساب إحصائيات اليوم
                income_data = Income.objects.filter(branch=branch, date=report_date)
                expense_data = Expense.objects.filter(branch=branch, date=report_date)
                
                total_income = income_data.aggregate(total=Sum('amount'))['total'] or 0
                total_expenses = expense_data.aggregate(total=Sum('amount'))['total'] or 0
                
                reg_income = income_data.filter(income_type='registration').aggregate(
                    total=Sum('amount')
                )['total'] or 0
                
                ins_income = income_data.filter(income_type='installment').aggregate(
                    total=Sum('amount')
                )['total'] or 0
                
                registration_count = income_data.filter(income_type='registration').count()
                installment_count = income_data.filter(income_type='installment').count()
                
                report_data = {
                    'date': report_date.strftime('%Y-%m-%d'),
                    'branch_name': branch.name,
                    'total_income': total_income,
                    'total_expenses': total_expenses,
                    'net': total_income - total_expenses,
                    'registration_income': reg_income,
                    'installment_income': ins_income,
                    'registration_count': registration_count,
                    'installment_count': installment_count,
                }
                
                # إرسال بالإيميل
                if manager.email:
                    success = send_daily_report_to_branch_manager(branch, manager.email, report_data)
                    if success:
                        total_sent_emails += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'✓ تم إرسال التقرير بالإيميل لـ {manager.get_full_name()} ({branch.name})'
                        ))
                
                # إرسال بالواتساب
                if manager.phone:
                    success = send_daily_summary_to_manager_whatsapp(manager, report_data)
                    if success:
                        total_sent_whatsapp += 1
                        
            except Exception as e:
                logger.error(f"Error sending report to {manager}: {e}")
                self.stderr.write(self.style.ERROR(
                    f'✗ فشل إرسال التقرير لـ {manager.get_full_name()}: {e}'
                ))

        # ========== 2. إرسال تقارير للمديرين الإقليميين ==========
        self.stdout.write(self.style.NOTICE('\n📧 جاري إرسال التقارير الإقليمية...'))
        
        regional_managers = User.objects.filter(
            user_type='regional_manager',
            is_active=True
        )

        for regional_manager in regional_managers:
            try:
                managed_branches = regional_manager.managed_branches.all()
                
                if not managed_branches.exists():
                    continue
                
                branches_data = []
                total_income = 0
                total_expenses = 0
                total_new_students = 0
                
                for branch in managed_branches:
                    income = Income.objects.filter(branch=branch, date=report_date).aggregate(
                        total=Sum('amount')
                    )['total'] or 0
                    
                    expenses = Expense.objects.filter(branch=branch, date=report_date).aggregate(
                        total=Sum('amount')
                    )['total'] or 0
                    
                    new_students = Income.objects.filter(
                        branch=branch, 
                        date=report_date,
                        income_type='registration'
                    ).count()
                    
                    branches_data.append({
                        'name': branch.name,
                        'income': income,
                        'expenses': expenses,
                        'net': income - expenses,
                        'new_students': new_students,
                    })
                    
                    total_income += income
                    total_expenses += expenses
                    total_new_students += new_students
                
                report_data = {
                    'date': report_date.strftime('%Y-%m-%d'),
                    'total_branches': managed_branches.count(),
                    'total_income': total_income,
                    'total_expenses': total_expenses,
                    'net_total': total_income - total_expenses,
                    'total_new_students': total_new_students,
                    'branches_data': branches_data,
                }
                
                if regional_manager.email:
                    success = send_daily_report_to_regional_manager(regional_manager, report_data)
                    if success:
                        total_sent_emails += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'✓ تم إرسال التقرير الإقليمي لـ {regional_manager.get_full_name()}'
                        ))
                        
            except Exception as e:
                logger.error(f"Error sending regional report to {regional_manager}: {e}")
                self.stderr.write(self.style.ERROR(
                    f'✗ فشل إرسال التقرير الإقليمي لـ {regional_manager.get_full_name()}: {e}'
                ))

        # ========== 3. إرسال التقرير الشامل للأدمن ==========
        self.stdout.write(self.style.NOTICE('\n📧 جاري إرسال التقرير الشامل للأدمن...'))
        
        try:
            # جمع كل الفروع
            all_branches = Branch.objects.filter(is_active=True)
            
            branches_data = []
            total_income = 0
            total_expenses = 0
            total_new_students = 0
            
            for branch in all_branches:
                income = Income.objects.filter(branch=branch, date=report_date).aggregate(
                    total=Sum('amount')
                )['total'] or 0
                
                expenses = Expense.objects.filter(branch=branch, date=report_date).aggregate(
                    total=Sum('amount')
                )['total'] or 0
                
                new_students = Income.objects.filter(
                    branch=branch, 
                    date=report_date,
                    income_type='registration'
                ).count()
                
                branches_data.append({
                    'name': branch.name,
                    'income': income,
                    'expenses': expenses,
                    'net': income - expenses,
                    'new_students': new_students,
                })
                
                total_income += income
                total_expenses += expenses
                total_new_students += new_students
            
            report_data = {
                'date': report_date.strftime('%Y-%m-%d'),
                'total_branches': all_branches.count(),
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_total': total_income - total_expenses,
                'total_new_students': total_new_students,
                'branches_data': branches_data,
            }
            
            # جمع إيميلات الأدمن
            admins = User.objects.filter(
                user_type='admin',
                is_active=True
            ) | User.objects.filter(
                is_superuser=True,
                is_active=True
            )
            
            admin_emails = [admin.email for admin in admins.distinct() if admin.email]
            
            if admin_emails:
                success = send_daily_report_to_admins(admin_emails, report_data)
                if success:
                    total_sent_emails += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ تم إرسال التقرير الشامل لـ {len(admin_emails)} أدمن'
                    ))
            else:
                self.stdout.write(self.style.WARNING(
                    '⚠ لا يوجد أدمن لديهم إيميل مسجل'
                ))
                
        except Exception as e:
            logger.error(f"Error sending admin report: {e}")
            self.stderr.write(self.style.ERROR(
                f'✗ فشل إرسال التقرير للأدمن: {e}'
            ))

        # ========== ملخص النتائج ==========
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'📊 تم الانتهاء من إرسال التقارير\n'
            f'{"="*60}\n'
            f'📧 إيميلات مرسلة: {total_sent_emails}\n'
            f'💬 واتساب مرسل: {total_sent_whatsapp}\n'
            f'📅 التاريخ: {report_date}\n'
            f'{"="*60}'
        ))
