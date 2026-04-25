"""
إدخال الدورات والدبلومات لمعهد الفاو
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_management.settings')
django.setup()
sys.stdout.reconfigure(encoding='utf-8')

from courses.models import Course
from branches.models import Branch

branch = Branch.objects.filter(id=6).first()  # فرع الرياض
if not branch:
    branch = Branch.objects.first()

courses_data = [
    # === دبلومات ===
    {'name': 'دبلوم الإدارة المكتبية', 'type': 'diploma', 'price': 3000, 'days': 120},
    {'name': 'دبلوم الموارد البشرية', 'type': 'diploma', 'price': 3500, 'days': 120},
    {'name': 'دبلوم علوم الحاسب الآلي التطبيقي', 'type': 'diploma', 'price': 4000, 'days': 150},
    {'name': 'دبلوم شبكات الحاسب', 'type': 'diploma', 'price': 4000, 'days': 150},
    {'name': 'دبلوم الأمن السيبراني', 'type': 'diploma', 'price': 4500, 'days': 150},
    {'name': 'دبلوم الحاسب وتقنيات المكاتب', 'type': 'diploma', 'price': 3500, 'days': 120},
    {'name': 'دبلوم إدارة المستشفيات والخدمات الصحية', 'type': 'diploma', 'price': 4000, 'days': 150},
    {'name': 'دبلوم إدارة الخدمات اللوجستية', 'type': 'diploma', 'price': 3500, 'days': 120},

    # === دورات ===
    {'name': 'دورة إدخال بيانات ومعالجة نصوص', 'type': 'course', 'price': 800, 'days': 30},
    {'name': 'دورة المحاسبة', 'type': 'course', 'price': 1200, 'days': 45},
    {'name': 'دورة استخدام الحاسب الآلي في الأعمال المكتبية', 'type': 'course', 'price': 1000, 'days': 30},
    {'name': 'دورة الإدارة المكتبية', 'type': 'course', 'price': 1000, 'days': 30},
    {'name': 'دورة الإدارة المكتبية المتقدمة', 'type': 'course', 'price': 1500, 'days': 45},
    {'name': 'IC3', 'type': 'course', 'price': 1200, 'days': 30},
    {'name': 'MOS', 'type': 'course', 'price': 1500, 'days': 30},
    {'name': 'الحاسب والإنترنت', 'type': 'course', 'price': 800, 'days': 20},
    {'name': 'تطبيقات الحاسب', 'type': 'course', 'price': 900, 'days': 25},
    {'name': 'تطبيقات الحاسب المكتبية والسكرتارية', 'type': 'course', 'price': 1200, 'days': 30},
    {'name': 'دورات تطويرية', 'type': 'course', 'price': 500, 'days': 15},
    {'name': 'PMP إدارة المشاريع', 'type': 'course', 'price': 2500, 'days': 60},
    {'name': 'دورة سلاسل الإمداد والتوريد', 'type': 'course', 'price': 1500, 'days': 30},
    {'name': 'دورة إدارة الموارد البشرية', 'type': 'course', 'price': 1500, 'days': 30},
]

created_count = 0
updated_count = 0

for idx, item in enumerate(courses_data, start=1):
    code = f"FAW-{item['type'].upper()[:3]}-{idx:03d}"
    course, created = Course.objects.update_or_create(
        name=item['name'],
        defaults={
            'code': code,
            'course_type': item['type'],
            'price': item['price'],
            'duration_days': item['days'],
            'is_active': True,
        }
    )
    if branch:
        course.branches.add(branch)
    if created:
        created_count += 1
    else:
        updated_count += 1

print(f"تم إنشاء {created_count} دورة/دبلومة جديدة")
print(f"تم تحديث {updated_count} موجودة")
print(f"الإجمالي: {created_count + updated_count}")
