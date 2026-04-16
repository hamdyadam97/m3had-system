#!/usr/bin/env python
"""
ملف Seed لإنشاء 11 فرع مع بيانات تجريبية كاملة:
- الفروع
- الموظفين
- الدورات
- الطلاب (كاش + أقساط)
- المتأخرات
- الدفعات والمصروفات

الأمر: python seed_11_branches.py
"""

import os
import sys
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_management.settings')

# Fix Windows console encoding for Arabic output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import django
django.setup()

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from branches.models import Branch, BranchTarget
from courses.models import Course
from students.models import Student, Enrollment
from students.installment_models import InstallmentPlan, Installment
from transactions.models import Income, Expense

# ---------------------------------------------------------------------------
# قوائم الأسماء السعودية
# ---------------------------------------------------------------------------
MALE_FIRST_NAMES = [
    "عبدالله", "أحمد", "محمد", "خالد", "سعد", "فهد", "سلطان", "نواف",
    "بندر", "تركي", "ياسر", "فيصل", "مشعل", "عمر", "طلال", "سالم",
    "ناصر", "منصور", "هاني", "رامي", "عبدالرحمن", "سامي", "وليد",
    "فواز", "ماجد", "عبدالعزيز", "سعود", "عبدالمجيد", "زياد", "مبارك",
    "ثامر", "عبدالله", "فيصل", "عبدالكريم", "صالح", "إبراهيم", "محسن",
    "عبدالإله", "هشام", "خالد", "ممدوح", "غازي", "عبدالفتاح", "مقرن"
]

FEMALE_FIRST_NAMES = [
    "سارة", "نورة", "فاطمة", "ليلى", "رنا", "هند", "منى", "دلال",
    "نوف", "لجين", "ريم", "جواهر", "أمل", "وجدان", "بسمة", "دانة",
    "شهد", "رغد", "amal", "لين", "جوري", "تالا", "ملاك", "سارة",
    "جمانة", "هيا", "الجوهرة", "ابتسام", "حصة", "موضي"
]

LAST_NAMES = [
    "العتيبي", "القحطاني", "الدوسري", "الشمري", "السبيعي", "الزهراني",
    "الحربي", "الغامدي", "الشهراني", "البلوي", "الفهدي", "الصيعري",
    "الحربي", "الحمدان", "الفيصل", "الراجحي", "السويلم", "الخراشي",
    "العنزي", "الحربي", "المطيري", "السهلي", "العجمي", "الحميد",
    "العبدالله", "السالم", "الخضير", "القاسم", "المالكي"
]

# ---------------------------------------------------------------------------
# الفروع
# ---------------------------------------------------------------------------
BRANCHES_DATA = [
    {"name": "الأهلي عرعر", "code": "AHA", "address": "عرعر - حي المروج - شارع الملك عبدالعزيز", "phone": "0500001001"},
    {"name": "الأهلي سكاكا", "code": "AHS", "address": "سكاكا - حي الروضة - طريق الملك فهد", "phone": "0500001002"},
    {"name": "الأهلي قريات", "code": "AHQ", "address": "قريات - شارع الأمير سلطان", "phone": "0500001003"},
    {"name": "الأهلي المنصورية", "code": "AHM", "address": "المنصورية - شارع التحلية", "phone": "0500001004"},
    {"name": "الثقة الدائمة", "code": "TD", "address": "الرياض - حي النزهة - شارع الثقة", "phone": "0500001005"},
    {"name": "المورد الوافي", "code": "MW", "address": "جدة - حي الصفا - شارع الستين", "phone": "0500001006"},
    {"name": "آفاق التطور", "code": "AT", "address": "الدمام - حي الشاطئ - شارع الأمير محمد", "phone": "0500001007"},
    {"name": "الفاو الرياض", "code": "FR", "address": "الرياض - حي العليا - طريق الملك فهد", "phone": "0500001008"},
    {"name": "الفاو القصيم", "code": "FQ", "address": "بريدة - حي النخيل - شارع الملك عبدالله", "phone": "0500001009"},
    {"name": "الفاو حفر الباطن", "code": "FHB", "address": "حفر الباطن - حي المحمدية - شارع الستين", "phone": "0500001010"},
    {"name": "خميس مشيط", "code": "KM", "address": "خميس مشيط - حي المدينة - شارع فلسطين", "phone": "0500001011"},
]

COURSE_NAMES = [
    "دبلوم المحاسبة المالية", "دبلوم الموارد البشرية", "دبلوم إدارة المشاريع",
    "دبلوم التسويق الرقمي", "دبلوم السكرتارية الطبية", "دبلوم إدارة المكاتب",
    "دبلوم اللغة الإنجليزية للأعمال", "دبلوم الجودة والإعتماد",
    "دورة Excel متقدم", "دورة تحليل البيانات", "دورة القيادة الإدارية",
    "دورة السلامة المهنية", "دورة اللغة الإنجليزية العامة", "دورة ICDL",
    "دورة التسويق الإلكتروني", "دورة إدارة الوقت", "دورة خدمة العملاء",
    "دورة الجرافيك ديزاين", "دورة السوشيال ميديا", "دورة إدارة المخزون"
]

EXPENSE_CATS = ["salaries", "rent", "utilities", "supplies", "marketing", "maintenance", "other"]
PAYMENT_METHODS = ["mada", "visa", "bank_transfer"]
PAYMENT_LOCATIONS = ["in_person", "remote"]

# ---------------------------------------------------------------------------
# دوال مساعدة
# ---------------------------------------------------------------------------

def random_phone():
    prefixes = ["050", "053", "054", "055", "056", "057", "058"]
    return random.choice(prefixes) + "".join([str(random.randint(0, 9)) for _ in range(7)])

def random_email(first, last):
    domains = ["gmail.com", "hotmail.com", "outlook.sa", "yahoo.com"]
    clean_first = first.replace(" ", "").replace("عبدال", "abdul")
    clean_last = last.replace("ال", "").replace(" ", "")
    return f"{clean_first}.{clean_last}{random.randint(1,999)}@{random.choice(domains)}"

def random_name(gender="male"):
    if gender == "female":
        return f"{random.choice(FEMALE_FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    return f"{random.choice(MALE_FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def random_date(start_days_ago=365, end_days_ago=30):
    return timezone.now().date() - timedelta(days=random.randint(end_days_ago, start_days_ago))

# ---------------------------------------------------------------------------
# خطوات الإنشاء
# ---------------------------------------------------------------------------

def create_branches():
    branches = []
    for data in BRANCHES_DATA:
        b, _ = Branch.objects.get_or_create(
            code=data["code"],
            defaults={
                "name": data["name"],
                "address": data["address"],
                "phone": data["phone"],
                "is_active": True,
            }
        )
        branches.append(b)
        # أهداف شهرية
        for m in range(1, 13):
            BranchTarget.objects.get_or_create(
                branch=b, year=2025, month=m,
                defaults={"amount": Decimal(random.randint(50000, 150000))}
            )
            BranchTarget.objects.get_or_create(
                branch=b, year=2026, month=m,
                defaults={"amount": Decimal(random.randint(50000, 150000))}
            )
    print(f"✅ تم إنشاء/تحديث {len(branches)} فرع")
    return branches


def create_courses(branches):
    courses = []
    for idx, name in enumerate(COURSE_NAMES, 1):
        c, _ = Course.objects.get_or_create(
            code=f"C{idx:03d}",
            defaults={
                "name": name,
                "course_type": "diploma" if "دبلوم" in name else "course",
                "description": f"{name} - برنامج تدريبي معتمد",
                "price": Decimal(random.randint(1500, 8000)),
                "duration_days": random.randint(30, 180),
                "is_active": True,
            }
        )
        # كل دورة متاحة في كل الفروع
        for b in branches:
            c.branches.add(b)
        courses.append(c)
    print(f"✅ تم إنشاء/تحديث {len(courses)} دورة")
    return courses


def create_users(branches):
    users = []
    # أولاً: admin عام
    admin, _ = User.objects.get_or_create(
        username="admin",
        defaults={
            "first_name": "مدير",
            "last_name": "النظام",
            "email": "admin@institute.sa",
            "user_type": "admin",
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        }
    )
    admin.set_password("admin123")
    admin.save()
    users.append(admin)

    for branch in branches:
        # مدير فرع
        fn, ln = random_name().split(" ", 1)
        bm, _ = User.objects.get_or_create(
            username=f"bm_{branch.code.lower()}",
            defaults={
                "first_name": fn,
                "last_name": ln,
                "email": random_email(fn, ln),
                "user_type": "branch_manager",
                "branch": branch,
                "phone": random_phone(),
                "is_active": True,
                "is_staff": True,
            }
        )
        bm.set_password("password123")
        bm.save()
        users.append(bm)

        # محاسب
        fn, ln = random_name().split(" ", 1)
        acc, _ = User.objects.get_or_create(
            username=f"acc_{branch.code.lower()}",
            defaults={
                "first_name": fn,
                "last_name": ln,
                "email": random_email(fn, ln),
                "user_type": "accountant",
                "branch": branch,
                "phone": random_phone(),
                "is_active": True,
            }
        )
        acc.set_password("password123")
        acc.save()
        users.append(acc)

        # 2-3 موظفين
        for i in range(random.randint(2, 3)):
            gender = random.choice(["male", "female"])
            fn, ln = random_name(gender).split(" ", 1)
            emp, _ = User.objects.get_or_create(
                username=f"emp_{branch.code.lower()}_{i+1}",
                defaults={
                    "first_name": fn,
                    "last_name": ln,
                    "email": random_email(fn, ln),
                    "user_type": "employee",
                    "branch": branch,
                    "phone": random_phone(),
                    "is_active": True,
                }
            )
            emp.set_password("password123")
            emp.save()
            users.append(emp)

    print(f"✅ تم إنشاء/تحديث {len(users)} مستخدم")
    return users


def create_students_and_data(branches, courses, users):
    created_students = 0
    created_incomes = 0
    created_expenses = 0
    created_overdue = 0

    # نجمع موظفي كل فرع
    branch_employees = {}
    for b in branches:
        branch_employees[b.id] = list(User.objects.filter(branch=b, user_type__in=["employee", "accountant", "branch_manager"]))

    for branch in branches:
        employees = branch_employees.get(branch.id, [])
        num_students = random.randint(15, 25)

        for s_idx in range(num_students):
            gender = random.choice(["male", "female"])
            full = random_name(gender)
            phone = random_phone()
            nat_id = str(random.randint(1000000000, 1999999999))

            # إنشاء Student أولاً
            student = Student.objects.create(
                full_name=full,
                phone=phone,
                email=random_email(full.split()[0], full.split()[-1]),
                national_id=nat_id,
                address=f"{branch.name} - حي عشوائي - شارع {random.randint(1,99)}",
                branch=branch,
                course=random.choice(courses),
                registration_date=random_date(400, 30),
                total_price=Decimal(0),  # سيتم التحديث لاحقاً
                payment_method="full",
                installment_count=1,
                installment_amount=Decimal(0),
                paid_installments=0,
                is_active=True,
            )
            created_students += 1

            # إنشاء Enrollment
            course = random.choice(courses)
            total_price = Decimal(random.randint(2000, 9000))
            payment_method = random.choice(["full", "installment"])
            installment_count = 1
            installment_amount = Decimal(0)
            first_inst_date = None

            if payment_method == "installment":
                installment_count = random.choice([2, 3, 4, 6])
                installment_amount = (total_price / installment_count).quantize(Decimal("0.01"))
                first_inst_date = student.registration_date + timedelta(days=random.randint(10, 30))

            enrollment = Enrollment.objects.create(
                student=student,
                course=course,
                branch=branch,
                enrollment_type="new",
                status="active",
                total_price=total_price,
                payment_method=payment_method,
                installment_count=installment_count,
                installment_amount=installment_amount,
                first_installment_date=first_inst_date,
                start_date=student.registration_date + timedelta(days=random.randint(3, 14)),
                end_date=student.registration_date + timedelta(days=random.randint(60, 180)),
            )

            # إنشاء InstallmentPlan + Installments
            if payment_method == "installment":
                plan = InstallmentPlan.objects.create(
                    student=student,
                    total_amount=total_price,
                    number_of_installments=installment_count,
                    installment_amount=installment_amount,
                    first_installment_date=first_inst_date,
                )
                plan.create_installments()

                # دفع بعض الأقساط
                installments = list(plan.installments.order_by("installment_number"))
                paid_count = random.randint(0, len(installments))
                # نضمن وجود متأخرات في بعض الحالات
                if random.random() < 0.35:  # 35% متأخر
                    paid_count = random.randint(0, max(0, len(installments) - 2))

                for inst in installments[:paid_count]:
                    inst.is_paid = True
                    inst.paid_date = inst.due_date + timedelta(days=random.randint(0, 3))
                    inst.paid_amount = inst.amount
                    inst.save()

                    Income.objects.create(
                        branch=branch,
                        date=inst.paid_date,
                        income_type="installment",
                        student=student,
                        course=course,
                        amount=inst.amount,
                        installment=inst,
                        payment_method=random.choice(PAYMENT_METHODS),
                        payment_location=random.choice(PAYMENT_LOCATIONS),
                        collected_by=random.choice(employees) if employees else None,
                    )
                    created_incomes += 1

                # عد الأقساط المتأخرة
                for inst in installments[paid_count:]:
                    if inst.due_date < timezone.now().date():
                        created_overdue += 1

                # تحديث paid_installments في Student
                student.paid_installments = paid_count
                student.save(update_fields=["paid_installments"])

            else:
                # دفع كامل (كاش)
                if random.random() < 0.85:  # 85% دفع الكاش فعلاً
                    Income.objects.create(
                        branch=branch,
                        date=student.registration_date + timedelta(days=random.randint(0, 5)),
                        income_type="registration",
                        student=student,
                        course=course,
                        amount=total_price,
                        payment_method=random.choice(PAYMENT_METHODS),
                        payment_location=random.choice(PAYMENT_LOCATIONS),
                        collected_by=random.choice(employees) if employees else None,
                    )
                    created_incomes += 1

        # إنشاء مصروفات للفرع
        for _ in range(random.randint(8, 15)):
            Expense.objects.create(
                branch=branch,
                date=random_date(365, 0),
                category=random.choice(EXPENSE_CATS),
                description=f"مصروفات {random.choice(['شهرية', 'أسبوعية', 'طارئة'])} - {branch.name}",
                amount=Decimal(random.randint(200, 8000)),
                created_by=random.choice(employees) if employees else None,
                receipt_number=f"R-{random.randint(1000,9999)}",
            )
            created_expenses += 1

    print(f"✅ تم إنشاء {created_students} طالب")
    print(f"✅ تم إنشاء {created_incomes} دفعة (Income)")
    print(f"✅ تم إنشاء {created_expenses} مصروف (Expense)")
    print(f"⚠️  عدد الأقساط المتأخرة: {created_overdue}")


# ---------------------------------------------------------------------------
# التنفيذ الرئيسي
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("بدء إنشاء بيانات الـ 11 فرع (Seed Data)")
    print("=" * 60)

    with transaction.atomic():
        branches = create_branches()
        courses = create_courses(branches)
        users = create_users(branches)
        create_students_and_data(branches, courses, users)

    print("=" * 60)
    print("✅ تم الانتهاء بنجاح!")
    print("=" * 60)


if __name__ == "__main__":
    main()
