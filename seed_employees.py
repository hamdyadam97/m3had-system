"""
إدخال بيانات موظفي معهد الفاو المتقدم العالي للتدريب بالرياض / قسم الرجال
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'institute_management.settings')
django.setup()

# إصلاح مشكلة الترميز في Windows
sys.stdout.reconfigure(encoding='utf-8')

from accounts.models import User
from branches.models import Branch

# تحديد الفرع (الرياض = id 6)
branch, _ = Branch.objects.get_or_create(id=6, defaults={'name': 'الرياض'})

# بيانات الموظفين
employees = [
    # الطاقم المعتمد
    {'name': 'محمد عودة', 'job_title': 'مشرف التدريب', 'id_number': '2349041141', 'phone': '502056149', 'insurance': 'الأهلي عرعر', 'approval': 'approved', 'email': 'moh-odeh@ararhni.com'},
    {'name': 'عايد العنزي', 'job_title': 'استقبال', 'id_number': '1127368932', 'phone': '545926438', 'insurance': 'الفاو الرياض', 'approval': 'approved', 'email': 'ayed.aleinizi@ararhni.com'},
    {'name': 'مشعل العنزي', 'job_title': 'استقبال', 'id_number': '1102673504', 'phone': '532145128', 'insurance': 'الفاو الرياض', 'approval': 'approved', 'email': 'mashal.awad@ararhni.com'},
    {'name': 'عبدالله مبارك حمد النيل', 'job_title': 'مدرب تقنية معلومات', 'id_number': '2530419205', 'phone': '553126115', 'insurance': 'الأهلي عرعر', 'approval': 'approved', 'email': 'abdo.18@ararhni.com'},
    {'name': 'مصطفي ربيع', 'job_title': 'مدرب موارد بشرية', 'id_number': '2591451493', 'phone': '569816905', 'insurance': 'الفاو الرياض', 'approval': 'approved', 'email': 'mustafaa.eabdalhakim@ararhni.com'},
    {'name': 'محمد حمدي', 'job_title': 'مدرب قدرات لفظي', 'id_number': '2588772661', 'phone': '562682245', 'insurance': 'الفاو حفرالباطن', 'approval': 'approved', 'email': 'muhammad.ajwa@ararhni.com'},
    {'name': 'ناصر عبدالله الطحيني', 'job_title': 'مدرب رياضيات-متعاون', 'id_number': '1045210208', 'phone': '591090190', 'insurance': 'متعاون / غير مضاف', 'approval': 'approved', 'email': 'nasser.altahini@ararhni.com'},
    {'name': 'خالد الشهري', 'job_title': 'مدرس ثقافة إسلامية', 'id_number': '1000517092', 'phone': '554133064', 'insurance': 'متعاون / غير مضاف', 'approval': 'approved', 'email': 'khaled.alshahri@ararhni.com'},
    {'name': 'خالد محمد ناصر', 'job_title': 'مدرس لغة', 'id_number': '2593389360', 'phone': '534693984', 'insurance': 'الثقة الدائمة', 'approval': 'pending', 'email': 'Khaled.naser@ararhni.com'},
    {'name': 'محمد محمود الليثي', 'job_title': 'مدرس قدرات كمي', 'id_number': '2527950469', 'phone': '558769435', 'insurance': 'افاق التطور', 'approval': 'pending', 'email': 'mohammed.ahmed@ararhni.com'},
    {'name': 'خيري علي احمد', 'job_title': 'محصل ومسوق', 'id_number': '2507620033', 'phone': '508911156', 'insurance': 'الفاو الرياض', 'approval': 'not_approved', 'email': 'khayri.ahmed@ararhni.com'},
    {'name': 'محمد خوجلي', 'job_title': 'مدرس لغة', 'id_number': '2313310712', 'phone': '533103739', 'insurance': 'الفاو حفرالباطن', 'approval': 'not_approved', 'email': 'mohammed_khougly@ararhni.com'},
    {'name': 'أحلام العتيبي', 'job_title': 'مدربه أعمال وإدارة', 'id_number': '1080538299', 'phone': '545309194', 'insurance': 'الفاو الرياض', 'approval': 'approved', 'email': 'ahlam.alotaibi@ararhni.com'},
    {'name': 'اثير العنزي', 'job_title': 'مدربة تقنية معلومات', 'id_number': '1103284574', 'phone': '554542835', 'insurance': 'الفاو الرياض', 'approval': 'pending', 'email': 'atheer_mohammad@ararhni.com'},
    # الطاقم الغير معتمد
    {'name': 'سلطان ثامر ساير العنزي', 'job_title': 'المسؤول العام للمعهد', 'id_number': '1079164370', 'phone': '567001024', 'insurance': 'لا يوجد', 'approval': 'not_approved', 'email': 'sultan.alanazi@ararhni.com'},
    {'name': 'لافي خليف العنزي', 'job_title': 'استقبال', 'id_number': '1084661014', 'phone': '555184557', 'insurance': 'لا يوجد', 'approval': 'not_approved', 'email': 'lafi_alenezi@ararhni.com'},
    {'name': 'محمد عواض الحارثي', 'job_title': 'مدرب تقنية معلومات', 'id_number': '1072184573', 'phone': '550427771', 'insurance': 'لا يوجد', 'approval': 'not_approved', 'email': 'mo.a.al-harthi@hotmail.com'},
    {'name': 'مد الإسلام', 'job_title': 'عامل النظافة', 'id_number': '2560321990', 'phone': '531324337', 'insurance': 'لا يوجد', 'approval': 'not_approved', 'email': 'md.alislam@ararhni.com'},
    {'name': 'ياسر يحيى عبدالله سليم', 'job_title': 'عامل النظافة', 'id_number': '2560321990', 'phone': '531324337', 'insurance': 'في انتظار نقل الكفالة', 'approval': 'not_approved', 'email': 'yaser.selim@ararhni.com'},
]


def split_name(full_name):
    """تقسيم الاسم إلى first_name و last_name"""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ''
    elif len(parts) == 2:
        return parts[0], parts[1]
    else:
        # أول كلمة first_name، الباقي last_name
        return parts[0], ' '.join(parts[1:])


created_count = 0
updated_count = 0

for emp in employees:
    first_name, last_name = split_name(emp['name'])
    email = emp['email'].strip()
    if not email or '@' not in email:
        email = f"emp_{emp['id_number']}@temp.local"

    username = emp['id_number']
    if User.objects.filter(username=username).exists():
        user = User.objects.get(username=username)
        updated_count += 1
    else:
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=username,  # كلمة المرور = رقم الهوية
        )
        created_count += 1

    user.job_title = emp['job_title']
    user.id_number = emp['id_number']
    user.phone = emp['phone']
    user.insurance_company = emp['insurance']
    user.approval_status = emp['approval']
    user.branch = branch
    user.user_type = 'employee'
    user.save()

print(f"تم إنشاء {created_count} موظف جديد")
print(f"تم تحديث {updated_count} موظف موجود")
print(f"الإجمالي: {created_count + updated_count}")
