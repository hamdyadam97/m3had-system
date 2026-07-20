import os
import tempfile
import pandas as pd
import logging
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db.models import Q
from django.db import transaction
from datetime import datetime

logger = logging.getLogger(__name__)
def parse_excel_preview(file_path, sheet_name=0):
    """قراءة كل صفوف ملف Excel لعرض preview"""
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        # نحول التواريخ لنص عشان نعرضهم
        preview = df.fillna('').astype(str)
        return preview.values.tolist(), list(preview.columns)
    except Exception as e:
        raise ValueError(f'خطأ في قراءة الملف: {str(e)}')


def detect_date_format(date_str):
    """محاولة تحديد تنسيق التاريخ"""
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except:
            continue
    return None


def clean_course_name(name):
    """تنظيف اسم الدورة للمطابقة الذكية"""
    import re
    name = str(name).strip()
    # إزالة كلمات مثل دبلوم، دورة، دورات، تطويرية
    name = re.sub(r'^(دبلوم|دورة|دورات|دبلومة|كورس|تطويرية)\s*', '', name)
    # إزالة "ال" التعريف من البداية
    name = re.sub(r'^ال', '', name)
    # إزالة المسافات الزائدة
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def find_course_id(course_raw, courses_cache):
    """البحث الذكي عن الدورة باستخدام matching مرن"""
    cleaned_raw = clean_course_name(course_raw)
    if not cleaned_raw:
        return None

    # محاولة 1: exact match على الاسم المنظف
    for cname, cid in courses_cache.items():
        cleaned_cname = clean_course_name(cname)
        if cleaned_raw == cleaned_cname:
            return cid

    # محاولة 2: contains (المنظف داخل المنظف)
    for cname, cid in courses_cache.items():
        cleaned_cname = clean_course_name(cname)
        if cleaned_raw in cleaned_cname or cleaned_cname in cleaned_raw:
            return cid

    # محاولة 3: fuzzy matching باستخدام difflib
    import difflib
    best_ratio = 0
    best_id = None
    for cname, cid in courses_cache.items():
        cleaned_cname = clean_course_name(cname)
        ratio = difflib.SequenceMatcher(None, cleaned_raw, cleaned_cname).ratio()
        if ratio > best_ratio and ratio >= 0.6:
            best_ratio = ratio
            best_id = cid

    return best_id


def clean_person_name(name):
    """تنظيف اسم الشخص للمطابقة الذكية"""
    import re
    name = str(name).strip()
    # إزالة الألقاب الشائعة
    name = re.sub(r'^(الأستاذ|أستاذ|الاستاذ|استاذ|أ\.|است\.|م\.|السيد|سيد)\s*', '', name)
    # إزالة المسافات الزائدة
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def find_collector_id(collector_raw, collectors_cache):
    """البحث الذكي عن المحصل باستخدام matching مرن"""
    cleaned_raw = clean_person_name(collector_raw)
    if not cleaned_raw:
        return None

    # محاولة 1: exact match
    for cname, cid in collectors_cache.items():
        if cleaned_raw == clean_person_name(cname):
            return cid

    # محاولة 2: contains
    for cname, cid in collectors_cache.items():
        cleaned_cname = clean_person_name(cname)
        if cleaned_raw in cleaned_cname or cleaned_cname in cleaned_raw:
            return cid

    # محاولة 3: fuzzy matching
    import difflib
    best_ratio = 0
    best_id = None
    for cname, cid in collectors_cache.items():
        cleaned_cname = clean_person_name(cname)
        ratio = difflib.SequenceMatcher(None, cleaned_raw, cleaned_cname).ratio()
        if ratio > best_ratio and ratio >= 0.5:
            best_ratio = ratio
            best_id = cid

    return best_id


def import_excel_data(file_path, mapping, branch, user):
    """استيراد بيانات من Excel حسب الـ mapping (مُحسّن بالـ bulk_create)"""
    from .models import Income
    from branches.models import Branch
    from courses.models import Course
    from accounts.models import User

    df = pd.read_excel(file_path, header=None)
    imported = 0
    errors = []
    income_objects = []

    # --- Cache للدورات والمحصلين (تجنب query لكل صف) ---
    courses_cache = {}
    for c in Course.objects.filter(is_active=True).values('id', 'name'):
        courses_cache[c['name']] = c['id']

    # دورات تم إنشاؤها تلقائياً خلال هذا الاستيراد
    created_courses = {}

    def create_course_if_missing(name, branch):
        """إنشاء دورة/دبلومة جديدة لو مش مسجلة"""
        import uuid
        name = name.strip()
        if not name:
            return None

        # محاولة العثور على الدورة بأقرب تطابق أولاً
        existing_id = find_course_id(name, courses_cache)
        if existing_id:
            return existing_id

        # لو تم إنشاؤها خلال هذا الاستيراد، استخدمها
        if name in created_courses:
            return created_courses[name]

        # تحديد نوع الدورة من اسمها
        course_type = 'diploma' if any(word in name for word in ['دبلوم', 'دبلومة']) else 'course'

        # إنشاء كود فريد
        code = f"AUTO-{uuid.uuid4().hex[:8].upper()}"

        course = Course.objects.create(
            name=name,
            code=code,
            course_type=course_type,
            price=0,
            duration_days=30,
            is_active=True,
        )
        course.branches.add(branch)

        # تحديث الكاش
        courses_cache[name] = course.id
        created_courses[name] = course.id
        return course.id

    collectors_cache = {}
    for u in User.objects.values('id', 'first_name', 'last_name', 'username'):
        collectors_cache[u['username']] = u['id']
        full = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip()
        if full:
            collectors_cache[full] = u['id']

    # --- قراءة البيانات بدون iterrows (أسرع) ---
    for idx, row in enumerate(df.values):
        try:
            values = row

            # الاسم
            party_name = ''
            if mapping.get('party_name') is not None:
                party_name = str(values[mapping['party_name']]).strip()
            if not party_name:
                continue

            # رقم الهوية / الملف
            id_number = ''
            if mapping.get('id_number') is not None:
                id_number = str(values[mapping['id_number']]).strip()

            # المبلغ
            amount = None
            if mapping.get('amount') is not None:
                try:
                    val = values[mapping['amount']]
                    if pd.notna(val):
                        amount = float(str(val).replace(',', ''))
                except:
                    pass
            if amount is None or amount <= 0:
                errors.append(f'صف {idx+1}: مبلغ غير صالح')
                continue

            # التاريخ
            date_val = None
            if mapping.get('date') is not None:
                raw_date = values[mapping['date']]
                if pd.notna(raw_date):
                    if isinstance(raw_date, datetime):
                        date_val = raw_date.date()
                    else:
                        date_val = detect_date_format(str(raw_date))
            if date_val is None:
                date_val = timezone.now().date()

            # نوع العملية: أي حاجة غير "تسجيل" تبقى قسط
            tx_type = ''
            if mapping.get('transaction_type') is not None:
                tx_type = str(values[mapping['transaction_type']]).strip()

            if 'تسجيل' in tx_type:
                income_type = 'registration'
            else:
                income_type = 'installment'

            # طريقة الدفع
            payment_method = 'mada'
            if mapping.get('payment_method') is not None:
                pm = str(values[mapping['payment_method']]).strip().lower()
                if 'فيزا' in pm or 'visa' in pm:
                    payment_method = 'visa'
                elif 'ماستر' in pm or 'master' in pm:
                    payment_method = 'mastercard'
                elif 'تحويل' in pm or 'bank' in pm:
                    payment_method = 'bank_transfer'

            # مدينة
            city = ''
            if mapping.get('city') is not None:
                city = str(values[mapping['city']]).strip()

            # محصل (من cache)
            collector = ''
            collected_by_user_id = user.id if user else None
            collector_found = False
            if mapping.get('collector_name') is not None:
                collector = str(values[mapping['collector_name']]).strip()
                if collector:
                    found_collector_id = find_collector_id(collector, collectors_cache)
                    if found_collector_id:
                        collected_by_user_id = found_collector_id
                        collector_found = True

            # لو المحصل غير موجود، يتسجل "لم يتم تعيينه" والمستخدم الحالي هو المحصل الافتراضي
            if not collector_found:
                collector = 'لم يتم تعيينه'
                collected_by_user_id = user.id if user else None

            # رقم العملية
            tx_num = ''
            if mapping.get('transaction_number') is not None:
                tx_num = str(values[mapping['transaction_number']]).strip()

            # الدورة / الدبلومة (من cache أو إنشاء تلقائي)
            course_id = None
            if mapping.get('course') is not None:
                course_raw = str(values[mapping['course']]).strip()
                if not course_raw:
                    errors.append(f'صف {idx+1}: لا يمكن إضافة سعر بدون إضافة دورة')
                    continue
                course_id = create_course_if_missing(course_raw, branch)
                if not course_id:
                    errors.append(f'صف {idx+1}: لا يمكن إنشاء الدورة "{course_raw}"')
                    continue

            # ملاحظات إضافية
            extra_notes = []
            if mapping.get('notes') is not None:
                note_val = values[mapping['notes']]
                if pd.notna(note_val) and str(note_val).strip():
                    extra_notes.append(str(note_val).strip())
            if city:
                extra_notes.append(f"المدينة: {city}")

            income_objects.append(Income(
                branch=branch,
                date=date_val,
                income_type=income_type,
                amount=amount,
                payment_method=payment_method,
                payment_location='in_person',
                collected_by_id=collected_by_user_id,
                party_name=party_name,
                id_number=id_number,
                collector_name=collector or (user.get_full_name() if user else ''),
                transaction_number=tx_num,
                course_id=course_id,
                notes='\n'.join(extra_notes),
            ))
            imported += 1

        except Exception as e:
            errors.append(f'صف {idx+1}: {str(e)}')

    # --- حفظ دفعة واحدة (أسرع بكثير) ---
    if income_objects:
        with transaction.atomic():
            created = Income.objects.bulk_create(income_objects, batch_size=500)
            logger.info(f"[Excel Import] User={user} | Branch={branch} | Prepared={len(income_objects)} | Created={len(created)}")
    else:
        logger.info(f"[Excel Import] User={user} | Branch={branch} | No valid rows to import")

    return imported, errors


def import_excel_expense_data(file_path, mapping, branch, user):
    """استيراد بيانات المصروفات من Excel حسب الـ mapping (مُحسّن)"""
    from .models import Expense

    df = pd.read_excel(file_path, header=None)
    imported = 0
    errors = []
    expense_objects = []

    category_map = {
        'رواتب': 'salaries',
        'إيجار': 'rent',
        'مرافق': 'utilities',
        'كهرباء': 'utilities',
        'مياه': 'utilities',
        'إنترنت': 'utilities',
        'مستلزمات': 'supplies',
        'تسويق': 'marketing',
        'صيانة': 'maintenance',
        'أخرى': 'other',
    }

    for idx, row in enumerate(df.values):
        try:
            values = row

            description = ''
            if mapping.get('description') is not None:
                description = str(values[mapping['description']]).strip()
            if not description:
                continue

            amount = None
            if mapping.get('amount') is not None:
                try:
                    val = values[mapping['amount']]
                    if pd.notna(val):
                        amount = float(str(val).replace(',', ''))
                except:
                    pass
            if amount is None or amount <= 0:
                errors.append(f'صف {idx+1}: مبلغ غير صالح')
                continue

            date_val = None
            if mapping.get('date') is not None:
                raw_date = values[mapping['date']]
                if pd.notna(raw_date):
                    if isinstance(raw_date, datetime):
                        date_val = raw_date.date()
                    else:
                        date_val = detect_date_format(str(raw_date))
            if date_val is None:
                date_val = timezone.now().date()

            category = 'other'
            if mapping.get('category') is not None:
                cat_raw = str(values[mapping['category']]).strip()
                for key, val in category_map.items():
                    if key in cat_raw:
                        category = val
                        break

            receipt = ''
            if mapping.get('receipt_number') is not None:
                receipt = str(values[mapping['receipt_number']]).strip()

            notes = ''
            if mapping.get('notes') is not None:
                note_val = values[mapping['notes']]
                if pd.notna(note_val) and str(note_val).strip():
                    notes = str(note_val).strip()

            expense_objects.append(Expense(
                branch=branch,
                date=date_val,
                category=category,
                description=description,
                amount=amount,
                receipt_number=receipt,
                notes=notes,
                created_by=user,
            ))
            imported += 1

        except Exception as e:
            errors.append(f'صف {idx+1}: {str(e)}')

    if expense_objects:
        with transaction.atomic():
            created = Expense.objects.bulk_create(expense_objects, batch_size=500)
            logger.info(f"[Excel Expense Import] User={user} | Branch={branch} | Prepared={len(expense_objects)} | Created={len(created)}")
    else:
        logger.info(f"[Excel Expense Import] User={user} | Branch={branch} | No valid rows to import")

    return imported, errors
