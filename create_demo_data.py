#!/usr/bin/env python
"""
سكربت لإنشاء بيانات تجريبية للنظام
"""

import os
import sys
import django

# إعداد Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_management.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import User
from branches.models import Branch
from courses.models import Course
from students.models import Student
from transactions.models import Income, Expense
from datetime import date, timedelta
import random


def create_branches():
    """إنشاء الفروع الـ 16"""
    branches_data = [
        {'name': 'فرع القاهرة الرئيسي', 'code': 'CAI01', 'monthly_target': 800000},
        {'name': 'فرع الجيزة', 'code': 'GIZ01', 'monthly_target': 600000},
        {'name': 'فرع الإسكندرية', 'code': 'ALX01', 'monthly_target': 700000},
        {'name': 'فرع طنطا', 'code': 'TAN01', 'monthly_target': 500000},
        {'name': 'فرع المنصورة', 'code': 'MAN01', 'monthly_target': 550000},
        {'name': 'فرع الزقازيق', 'code': 'ZAG01', 'monthly_target': 450000},
        {'name': 'فرع دمنهور', 'code': 'DAM01', 'monthly_target': 400000},
        {'name': 'فرع بنها', 'code': 'BAN01', 'monthly_target': 420000},
        {'name': 'فرع كفر الشيخ', 'code': 'KAF01', 'monthly_target': 380000},
        {'name': 'فرع المنيا', 'code': 'MIN01', 'monthly_target': 350000},
        {'name': 'فرع أسيوط', 'code': 'ASY01', 'monthly_target': 320000},
        {'name': 'فرع سوهاج', 'code': 'SOH01', 'monthly_target': 300000},
        {'name': 'فرع قنا', 'code': 'QEN01', 'monthly_target': 280000},
        {'name': 'فرع الأقصر', 'code': 'LUX01', 'monthly_target': 250000},
        {'name': 'فرع أسوان', 'code': 'ASW01', 'monthly_target': 220000},
        {'name': 'فرع بورسعيد', 'code': 'POR01', 'monthly_target': 480000},
    ]
    
    branches = []
    for data in branches_data:
        branch, created = Branch.objects.get_or_create(
            code=data['code'],
            defaults=data
        )
        branches.append(branch)
        if created:
            print(f"✓ تم إنشاء الفرع: {branch.name}")
        else:
            print(f"✓ الفرع موجود: {branch.name}")
    
    return branches


def create_courses():
    """إنشاء الدورات والدبلومات"""
    courses_data = [
        # دبلومات
        {'name': 'دبلومة البرمجة المتكاملة', 'code': 'DIP001', 'course_type': 'diploma', 'price': 15000, 'duration_days': 180},
        {'name': 'دبلومة الجرافيك ديزاين', 'code': 'DIP002', 'course_type': 'diploma', 'price': 12000, 'duration_days': 120},
        {'name': 'دبلومة اللغة الإنجليزية', 'code': 'DIP003', 'course_type': 'diploma', 'price': 8000, 'duration_days': 90},
        {'name': 'دبلومة المحاسبة المالية', 'code': 'DIP004', 'course_type': 'diploma', 'price': 10000, 'duration_days': 120},
        
        # دورات
        {'name': 'دورة Python للمبتدئين', 'code': 'CRS001', 'course_type': 'course', 'price': 3000, 'duration_days': 30},
        {'name': 'دورة تطوير الويب', 'code': 'CRS002', 'course_type': 'course', 'price': 4000, 'duration_days': 45},
        {'name': 'دورة Photoshop', 'code': 'CRS003', 'course_type': 'course', 'price': 2500, 'duration_days': 20},
        {'name': 'دورة ICDL', 'code': 'CRS004', 'course_type': 'course', 'price': 2000, 'duration_days': 30},
        {'name': 'دورة اللغة الإنجليزية المكثفة', 'code': 'CRS005', 'course_type': 'course', 'price': 3500, 'duration_days': 60},
        {'name': 'دورة إدارة الأعمال', 'code': 'CRS006', 'course_type': 'course', 'price': 2800, 'duration_days': 30},
    ]
    
    courses = []
    for data in courses_data:
        course, created = Course.objects.get_or_create(
            code=data['code'],
            defaults=data
        )
        courses.append(course)
        if created:
            print(f"✓ تم إنشاء الدورة: {course.name}")
        else:
            print(f"✓ الدورة موجودة: {course.name}")
    
    return courses


def create_users(branches):
    """إنشاء المستخدمين"""
    # المدير العام
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'first_name': 'المدير',
            'last_name': 'العام',
            'user_type': 'admin',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"✓ تم إنشاء المستخدم: {admin_user.username} (كلمة المرور: admin123)")
    else:
        print(f"✓ المستخدم موجود: {admin_user.username}")
    
    # مديرو الفروع
    for i, branch in enumerate(branches[:5], 1):
        username = f'manager{i}'
        manager, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': f'مدير',
                'last_name': f'فرع {branch.name}',
                'user_type': 'branch_manager',
                'branch': branch,
                'is_staff': True,
            }
        )
        if created:
            manager.set_password('manager123')
            manager.save()
            print(f"✓ تم إنشاء المستخدم: {manager.username} (كلمة المرور: manager123)")
    
    # موظفو الفروع
    for i, branch in enumerate(branches[:8], 1):
        username = f'employee{i}'
        employee, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': f'موظف',
                'last_name': str(i),
                'user_type': 'employee',
                'branch': branch,
            }
        )
        if created:
            employee.set_password('employee123')
            employee.save()
            print(f"✓ تم إنشاء المستخدم: {employee.username} (كلمة المرور: employee123)")
    
    return admin_user


def create_students(branches, courses):
    """إنشاء طلاب تجريبيين"""
    first_names = ['أحمد', 'محمد', 'علي', 'محمود', 'عمر', 'خالد', 'مصطفى', 'إبراهيم', 'يوسف', 'عبدالله',
                   'فاطمة', 'مريم', 'آية', 'نور', 'سارة', 'هنا', 'ملك', 'جنى', 'ليلى', 'سلمى']
    last_names = ['محمد', 'أحمد', 'علي', 'محمود', 'عمر', 'خالد', 'مصطفى', 'إبراهيم', 'عبدالله', 'حسن']
    
    students = []
    for i in range(50):  # 50 طالب تجريبي
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        branch = random.choice(branches)
        course = random.choice(courses)
        
        student = Student.objects.create(
            full_name=f'{first_name} {last_name}',
            phone=f'01{random.randint(0, 2)}{random.randint(10000000, 99999999)}',
            email=f'student{i+1}@example.com',
            branch=branch,
            course=course,
            total_price=course.price,
            payment_method=random.choice(['cash', 'installment']),
            payment_location=random.choice(['in_person', 'remote']),
            installment_count=random.choice([1, 2, 3, 4]) if random.random() > 0.5 else 1,
        )
        students.append(student)
    
    print(f"✓ تم إنشاء {len(students)} طالب تجريبي")
    return students


def create_transactions(branches, students, users):
    """إنشاء معاملات مالية تجريبية"""
    today = date.today()
    
    # إنشاء إيرادات للأيام الـ 30 الماضية
    for day_offset in range(30):
        transaction_date = today - timedelta(days=day_offset)
        
        for branch in branches[:5]:  # للفروع الخمسة الأولى فقط
            # إنشاء 3-7 إيرادات يومياً
            # داخل دالة create_transactions
            for _ in range(random.randint(3, 7)):
                branch_students = [s for s in students if s.branch == branch]
                if not branch_students:
                    continue

                student = random.choice(branch_students)
                income_type = random.choice(['registration', 'installment'])

                # تحويل Decimal إلى float لإجراء العملية الحسابية مع random
                price_as_float = float(student.total_price)

                if income_type == 'registration':
                    # حساب الدفعة الأولى (بين 30% إلى 50%)
                    amount = price_as_float * random.uniform(0.3, 0.5)
                else:
                    # حساب القسط بناءً على عدد الأقساط (تجنب القسمة على صفر)
                    div = student.installment_count if student.installment_count > 0 else 1
                    amount = price_as_float / div

                # عند الإنشاء، سيقوم Django بتحويل الـ float المحسوب تلقائياً إلى Decimal
                Income.objects.create(
                    branch=branch,
                    date=transaction_date,
                    income_type=income_type,
                    student=student,
                    course=student.course,
                    amount=round(amount, 2),  # تقريب لخانين عشريتين
                    payment_method=random.choice(['cash', 'visa', 'bank_transfer']),
                    payment_location=random.choice(['in_person', 'remote']),
                    collected_by=random.choice([u for u in users if u.branch == branch]),
                )
            
            # إنشاء 1-3 مصروفات يومياً
            for _ in range(random.randint(1, 3)):
                Expense.objects.create(
                    branch=branch,
                    date=transaction_date,
                    category=random.choice(['salaries', 'rent', 'utilities', 'supplies', 'marketing']),
                    description=f'مصروفات {transaction_date}',
                    amount=random.randint(500, 5000),
                    created_by=random.choice([u for u in users if u.branch == branch]),
                )
    
    print(f"✓ تم إنشاء المعاملات المالية لآخر 30 يوم")


def main():
    print("=" * 60)
    print("بدء إنشاء البيانات التجريبية...")
    print("=" * 60)
    
    # إنشاء الفروع
    branches = create_branches()
    
    # إنشاء الدورات
    courses = create_courses()
    
    # ربط الدورات بالفروع
    for course in courses:
        course.branches.set(branches)
        course.save()
    print(f"✓ تم ربط الدورات بالفروع")
    
    # إنشاء المستخدمين
    admin_user = create_users(branches)
    
    # إنشاء الطلاب
    students = create_students(branches, courses)
    
    # إنشاء المعاملات المالية
    users = list(User.objects.filter(branch__in=branches))
    create_transactions(branches, students, users)
    
    print("=" * 60)
    print("تم إنشاء البيانات التجريبية بنجاح!")
    print("=" * 60)
    print("\nبيانات تسجيل الدخول:")
    print("  - المدير العام: username='admin', password='admin123'")
    print("  - مديرو الفروع: username='manager1-5', password='manager123'")
    print("  - الموظفون: username='employee1-8', password='employee123'")
    print("=" * 60)


if __name__ == '__main__':
    main()
