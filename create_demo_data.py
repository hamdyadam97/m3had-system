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
from branches.models import Branch, BranchTarget
from courses.models import Course
from students.models import Student
from students.installment_models import InstallmentPlan, Installment
from transactions.models import Income, Expense
from datetime import date, timedelta
from decimal import Decimal
import random


def create_branches():
    """إنشاء الفروع الـ 16"""
    branches_data = [
        {'name': 'فرع القاهرة الرئيسي', 'code': 'CAI01', 'address': 'شارع التحرير، القاهرة', 'phone': '0223456789'},
        {'name': 'فرع الجيزة', 'code': 'GIZ01', 'address': 'شارع الهرم، الجيزة', 'phone': '0234567890'},
        {'name': 'فرع الإسكندرية', 'code': 'ALX01', 'address': 'شارع سعد زغلول، الإسكندرية', 'phone': '0345678901'},
        {'name': 'فرع طنطا', 'code': 'TAN01', 'address': 'شارع الجيش، طنطا', 'phone': '0403456789'},
        {'name': 'فرع المنصورة', 'code': 'MAN01', 'address': 'شارع الجيش، المنصورة', 'phone': '0502345678'},
        {'name': 'فرع الزقازيق', 'code': 'ZAG01', 'address': 'شارع جمال عبدالناصر، الزقازيق', 'phone': '0551234567'},
        {'name': 'فرع دمنهور', 'code': 'DAM01', 'address': 'شارع سعد زغلول، دمنهور', 'phone': '0456789012'},
        {'name': 'فرع بنها', 'code': 'BAN01', 'address': 'شارع الجمهورية، بنها', 'phone': '0132345678'},
        {'name': 'فرع كفر الشيخ', 'code': 'KAF01', 'address': 'شارع الجيش، كفر الشيخ', 'phone': '0471234567'},
        {'name': 'فرع المنيا', 'code': 'MIN01', 'address': 'شارع الجمهورية، المنيا', 'phone': '0861234567'},
        {'name': 'فرع أسيوط', 'code': 'ASY01', 'address': 'شارع الجمهورية، أسيوط', 'phone': '0881234567'},
        {'name': 'فرع سوهاج', 'code': 'SOH01', 'address': 'شارع الجمهورية، سوهاج', 'phone': '0931234567'},
        {'name': 'فرع قنا', 'code': 'QEN01', 'address': 'شارع الجمهورية، قنا', 'phone': '0961234567'},
        {'name': 'فرع الأقصر', 'code': 'LUX01', 'address': 'شارع الجمهورية، الأقصر', 'phone': '0951234567'},
        {'name': 'فرع أسوان', 'code': 'ASW01', 'address': 'شارع الجمهورية، أسوان', 'phone': '0971234567'},
        {'name': 'فرع بورسعيد', 'code': 'POR01', 'address': 'شارع فلسطين، بورسعيد', 'phone': '0661234567'},
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


def create_branch_targets(branches):
    """إنشاء أهداف شهرية للفروع"""
    today = date.today()
    targets = [
        800000, 600000, 700000, 500000, 550000,
        450000, 400000, 420000, 380000, 350000,
        320000, 300000, 280000, 250000, 220000, 480000
    ]
    
    for branch, target in zip(branches, targets):
        BranchTarget.objects.get_or_create(
            branch=branch,
            year=today.year,
            month=today.month,
            defaults={'amount': target}
        )
    print(f"✓ تم إنشاء الأهداف الشهرية للفروع")


def create_courses():
    """إنشاء الدورات والدبلومات"""
    courses_data = [
        # دبلومات
        {'name': 'دبلومة البرمجة المتكاملة', 'code': 'DIP001', 'course_type': 'diploma', 'price': 15000, 'duration_days': 180},
        {'name': 'دبلومة الجرافيك ديزاين', 'code': 'DIP002', 'course_type': 'diploma', 'price': 12000, 'duration_days': 120},
        {'name': 'دبلومة اللغة الإنجليزية', 'code': 'DIP003', 'course_type': 'diploma', 'price': 8000, 'duration_days': 90},
        {'name': 'دبلومة المحاسبة المالية', 'code': 'DIP004', 'course_type': 'diploma', 'price': 10000, 'duration_days': 120},
        {'name': 'دبلومة التسويق الرقمي', 'code': 'DIP005', 'course_type': 'diploma', 'price': 9000, 'duration_days': 100},
        
        # دورات
        {'name': 'دورة Python للمبتدئين', 'code': 'CRS001', 'course_type': 'course', 'price': 3500, 'duration_days': 30},
        {'name': 'دورة تطوير الويب Django', 'code': 'CRS002', 'course_type': 'course', 'price': 4500, 'duration_days': 45},
        {'name': 'دورة Photoshop', 'code': 'CRS003', 'course_type': 'course', 'price': 2500, 'duration_days': 20},
        {'name': 'دورة ICDL', 'code': 'CRS004', 'course_type': 'course', 'price': 2000, 'duration_days': 30},
        {'name': 'دورة اللغة الإنجليزية المكثفة', 'code': 'CRS005', 'course_type': 'course', 'price': 3500, 'duration_days': 60},
        {'name': 'دورة إدارة الأعمال', 'code': 'CRS006', 'course_type': 'course', 'price': 2800, 'duration_days': 30},
        {'name': 'دورة Excel المتقدم', 'code': 'CRS007', 'course_type': 'course', 'price': 1800, 'duration_days': 15},
        {'name': 'دورة اليوتيوب والمحتوى', 'code': 'CRS008', 'course_type': 'course', 'price': 2200, 'duration_days': 20},
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
    """إنشاء المستخدمين بأنواعهم المختلفة"""
    users = []
    
    # 1. المدير العام
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'first_name': 'المدير',
            'last_name': 'العام',
            'user_type': 'admin',
            'is_staff': True,
            'is_superuser': True,
            'phone': '01001234567'
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"✓ تم إنشاء المستخدم: {admin_user.username} (كلمة المرور: admin123)")
    else:
        print(f"✓ المستخدم موجود: {admin_user.username}")
    users.append(admin_user)
    
    # 2. مديرو الفروع
    for i, branch in enumerate(branches[:8], 1):
        username = f'manager{i}'
        manager, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': f'مدير',
                'last_name': f'فرع {i}',
                'user_type': 'branch_manager',
                'branch': branch,
                'is_staff': True,
                'phone': f'0101234567{i}'
            }
        )
        if created:
            manager.set_password('manager123')
            manager.save()
            print(f"✓ تم إنشاء المستخدم: {manager.username} (كلمة المرور: manager123)")
            users.append(manager)
    
    # 3. الموظفين
    for i, branch in enumerate(branches[:12], 1):
        username = f'employee{i}'
        employee, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': f'موظف',
                'last_name': str(i),
                'user_type': 'employee',
                'branch': branch,
                'phone': f'0109876543{i}'
            }
        )
        if created:
            employee.set_password('employee123')
            employee.save()
            print(f"✓ تم إنشاء المستخدم: {employee.username} (كلمة المرور: employee123)")
            users.append(employee)
    
    # 4. المحاسبين
    for i in range(1, 4):
        username = f'accountant{i}'
        accountant, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': 'محاسب',
                'last_name': str(i),
                'user_type': 'accountant',
                'is_staff': True,
                'phone': f'0105555666{i}'
            }
        )
        if created:
            accountant.set_password('accountant123')
            accountant.save()
            print(f"✓ تم إنشاء المستخدم: {accountant.username} (كلمة المرور: accountant123)")
            users.append(accountant)
    
    # 5. مدير إقليمي
    regional_manager, created = User.objects.get_or_create(
        username='regional1',
        defaults={
            'first_name': 'المدير',
            'last_name': 'الإقليمي',
            'user_type': 'regional_manager',
            'phone': '01011112222'
        }
    )
    if created:
        regional_manager.set_password('regional123')
        regional_manager.save()
        # ربطه بعدد من الفروع
        regional_manager.managed_branches.set(branches[:6])
        print(f"✓ تم إنشاء المستخدم: {regional_manager.username} (كلمة المرور: regional123)")
        users.append(regional_manager)
    
    return users


def create_students(branches, courses):
    """إنشاء طلاب تجريبيين مع خطط تقسيط"""
    first_names = ['أحمد', 'محمد', 'علي', 'محمود', 'عمر', 'خالد', 'مصطفى', 'إبراهيم', 'يوسف', 'عبدالله',
                   'فاطمة', 'مريم', 'آية', 'نور', 'سارة', 'هنا', 'ملك', 'جنى', 'ليلى', 'سلمى',
                   'ياسين', 'عبدالرحمن', 'حسن', 'سيد', 'كريم', 'نورا', 'هدى', 'ريم', 'شهد', 'أمينة']
    last_names = ['محمد', 'أحمد', 'علي', 'محمود', 'عمر', 'خالد', 'مصطفى', 'إبراهيم', 'عبدالله', 'حسن',
                  'عبدالعزيز', 'السيد', 'حسني', 'فؤاد', 'مجدي', 'رمضان', 'عادل', 'صالح', 'نصر', 'فتحي']
    
    students = []
    today = date.today()
    
    # إنشاء 80 طالب
    for i in range(80):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        branch = random.choice(branches)
        course = random.choice(courses)
        
        # تحديد طريقة الدفع
        payment_method = random.choice(['full', 'installment'])
        
        # إعداد بيانات الطالب الأساسية
        student_data = {
            'full_name': f'{first_name} {last_name}',
            'phone': f'01{random.randint(0, 2)}{random.randint(10000000, 99999999)}',
            'email': f'student{i+1}@example.com',
            'national_id': f'{random.randint(1000000000000, 2999999999999)}',
            'address': f'عنوان الطالب {i+1}، {branch.name}',
            'branch': branch,
            'course': course,
            'total_price': course.price,
            'payment_method': payment_method,
        }
        
        # إعداد بيانات الأقساط
        if payment_method == 'installment':
            installment_count = random.choice([2, 3, 4, 6])
            installment_amount = float(course.price) / installment_count
            first_installment_date = today - timedelta(days=random.randint(0, 60))
            
            student_data.update({
                'installment_count': installment_count,
                'installment_amount': round(installment_amount, 2),
                'first_installment_date': first_installment_date,
                'paid_installments': random.randint(0, installment_count - 1),
            })
        else:
            student_data.update({
                'installment_count': 1,
                'installment_amount': course.price,
            })
        
        student = Student.objects.create(**student_data)
        students.append(student)
        
        # إنشاء خطة تقسيط للطلاب بالتقسيط
        if payment_method == 'installment':
            plan = InstallmentPlan.objects.create(
                student=student,
                total_amount=course.price,
                number_of_installments=student.installment_count,
                installment_amount=student.installment_amount,
                first_installment_date=student.first_installment_date
            )
            # إنشاء الأقساط
            plan.create_installments()
            
            # دفع بعض الأقساط
            paid_count = student.paid_installments
            for installment in plan.installments.all()[:paid_count]:
                installment.is_paid = True
                installment.paid_date = first_installment_date + timedelta(days=30 * (installment.installment_number - 1))
                installment.paid_amount = installment.amount
                installment.save()
    
    print(f"✓ تم إنشاء {len(students)} طالب تجريبي")
    return students


def create_transactions(branches, students, users):
    """إنشاء معاملات مالية تجريبية"""
    today = date.today()
    
    employees = [u for u in users if u.user_type == 'employee']
    managers = [u for u in users if u.user_type == 'branch_manager']
    collectors = employees + managers
    
    total_income = 0
    total_expense = 0
    
    # إنشاء إيرادات للأيام الـ 60 الماضية
    for day_offset in range(60):
        transaction_date = today - timedelta(days=day_offset)
        
        for branch in branches:
            # 5-10 إيرادات يومياً للفرع
            branch_students = [s for s in students if s.branch == branch]
            if not branch_students:
                continue
                
            for _ in range(random.randint(5, 10)):
                student = random.choice(branch_students)
                
                # تحديد نوع الإيراد
                if student.is_new_registration():
                    income_type = 'registration'
                elif student.can_pay_installment():
                    income_type = 'installment'
                else:
                    continue  # الطالب مسدد بالكامل
                
                price_as_float = float(student.total_price)
                
                if income_type == 'registration':
                    # الدفعة الأولى 30-50%
                    amount = price_as_float * random.uniform(0.3, 0.5)
                else:
                    # قيمة القسط
                    div = student.installment_count if student.installment_count > 0 else 1
                    amount = price_as_float / div
                
                # تحديد المحصل
                branch_collectors = [c for c in collectors if c.branch == branch]
                collector = random.choice(branch_collectors) if branch_collectors else None
                
                income = Income.objects.create(
                    branch=branch,
                    date=transaction_date,
                    income_type=income_type,
                    student=student,
                    course=student.course,
                    amount=round(amount, 2),
                    payment_method=random.choice(['mada', 'visa', 'bank_transfer']),
                    payment_location=random.choice(['in_person', 'remote']),
                    collected_by=collector,
                    notes=f'{income_type} - {transaction_date}' if random.random() > 0.7 else ''
                )
                total_income += float(income.amount)
            
            # 2-5 مصروفات يومياً للفرع
            expense_categories = ['salaries', 'rent', 'utilities', 'supplies', 'marketing', 'maintenance', 'other']
            for _ in range(random.randint(2, 5)):
                category = random.choice(expense_categories)
                category_names = {
                    'salaries': 'رواتب الموظفين',
                    'rent': 'إيجار الفرع',
                    'utilities': 'فواتير كهرباء وماء',
                    'supplies': 'مستلزمات مكتبية',
                    'marketing': 'حملة تسويقية',
                    'maintenance': 'صيانة أجهزة',
                    'other': 'مصروفات متنوعة'
                }
                
                amount = random.randint(500, 8000)
                expense = Expense.objects.create(
                    branch=branch,
                    date=transaction_date,
                    category=category,
                    description=f'{category_names[category]} - {transaction_date}',
                    amount=amount,
                    created_by=random.choice(branch_collectors) if branch_collectors else None,
                    receipt_number=f'RCP-{random.randint(1000, 9999)}' if random.random() > 0.3 else '',
                    notes='تم السداد' if random.random() > 0.5 else ''
                )
                total_expense += float(expense.amount)
    
    print(f"✓ تم إنشاء المعاملات المالية لآخر 60 يوم")
    print(f"  - إجمالي الإيرادات: {total_income:,.2f} ر.س")
    print(f"  - إجمالي المصروفات: {total_expense:,.2f} ر.س")
    print(f"  - الصافي: {(total_income - total_expense):,.2f} ر.س")


def print_summary():
    """طباعة ملخص للبيانات"""
    print("\n" + "=" * 60)
    print("📊 ملخص البيانات في النظام:")
    print("=" * 60)
    print(f"  الفروع: {Branch.objects.count()}")
    print(f"  الدورات والدبلومات: {Course.objects.count()}")
    print(f"  المستخدمين: {User.objects.count()}")
    print(f"  الطلاب: {Student.objects.count()}")
    print(f"  خطط التقسيط: {InstallmentPlan.objects.count()}")
    print(f"  الأقساط: {Installment.objects.count()}")
    print(f"  الإيرادات: {Income.objects.count()}")
    print(f"  المصروفات: {Expense.objects.count()}")
    print("=" * 60)


def main():
    print("=" * 60)
    print("🚀 بدء إنشاء البيانات التجريبية...")
    print("=" * 60)
    
    # 1. إنشاء الفروع
    branches = create_branches()
    
    # 2. إنشاء الأهداف الشهرية
    create_branch_targets(branches)
    
    # 3. إنشاء الدورات
    courses = create_courses()
    
    # 4. ربط الدورات بالفروع
    for course in courses:
        # كل دورة متاحة في 8-12 فرع عشوائي
        selected_branches = random.sample(branches, random.randint(8, 12))
        course.branches.set(selected_branches)
    print(f"✓ تم ربط الدورات بالفروع")
    
    # 5. إنشاء المستخدمين
    users = create_users(branches)
    
    # 6. إنشاء الطلاب مع خطط التقسيط
    students = create_students(branches, courses)
    
    # 7. إنشاء المعاملات المالية
    create_transactions(branches, students, users)
    
    # طباعة الملخص
    print_summary()
    
    print("\n" + "=" * 60)
    print("✅ تم إنشاء البيانات التجريبية بنجاح!")
    print("=" * 60)
    print("\n🔑 بيانات تسجيل الدخول:")
    print("  ┌─────────────────────┬─────────────────┬────────────────────┐")
    print("  │ الدور               │ اسم المستخدم    │ كلمة المرور        │")
    print("  ├─────────────────────┼─────────────────┼────────────────────┤")
    print("  │ المدير العام        │ admin           │ admin123           │")
    print("  │ المدير الإقليمي     │ regional1       │ regional123        │")
    print("  │ مديرو الفروع        │ manager1-8      │ manager123         │")
    print("  │ الموظفين            │ employee1-12    │ employee123        │")
    print("  │ المحاسبين           │ accountant1-3   │ accountant123      │")
    print("  └─────────────────────┴─────────────────┴────────────────────┘")
    print("=" * 60)


if __name__ == '__main__':
    main()
