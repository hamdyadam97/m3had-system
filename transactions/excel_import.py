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


def safe_str(val):
    """يحول قيمة خلية Excel لنص، ومعاملة الخلايا الفارغة/NaN كنص فارغ حقيقي
    (str(nan) بترجع 'nan' كنص غير فارغ لو ماتعامل معاها كده أول حاجة)"""
    if pd.isna(val):
        return ''
    return str(val).strip()


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


def find_course_id(course_raw, courses_cache, always_pick_closest=False):
    """البحث الذكي عن الدورة باستخدام matching مرن.

    always_pick_closest: لو معملش ولا حد من محاولات المطابقة الدقيقة نتيجة،
    بيرجع أقرب دورة موجودة في النظام حتى لو نسبة التشابه ضعيفة (بدل ما يرفض الصف).
    """
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
    min_ratio = 0 if always_pick_closest else 0.6
    best_ratio = 0
    best_id = None
    for cname, cid in courses_cache.items():
        cleaned_cname = clean_course_name(cname)
        ratio = difflib.SequenceMatcher(None, cleaned_raw, cleaned_cname).ratio()
        if ratio > best_ratio and ratio >= min_ratio:
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
    # الدورات مشتركة بين كل الفروع، فبنطابق على كل الدورات النشطة مباشرة
    courses_cache = {c['name']: c['id'] for c in Course.objects.filter(is_active=True).values('id', 'name')}

    # المحصل لازم يكون من طاقم العمل. بنفضل مطابقته داخل نفس فرع الاستيراد الأول
    # (تقليل احتمال مطابقة اسم شبيه لموظف في فرع تاني بالغلط)، ولو مفيش تطابق
    # داخل الفرع بنرجع نبحث في كل الموظفين (لحالة موظف بيحصل لفرع غير فرعه الأساسي)
    def build_collectors_cache(qs):
        cache = {}
        for u in qs.values('id', 'first_name', 'last_name', 'username'):
            cache[u['username']] = u['id']
            full = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip()
            if full:
                cache[full] = u['id']
        return cache

    staff_qs = User.objects.filter(is_active=True, user_type__in=['employee', 'branch_manager', 'accountant'])
    collectors_cache_branch = build_collectors_cache(staff_qs.filter(branch=branch))
    collectors_cache_all = build_collectors_cache(staff_qs)

    # --- قراءة البيانات بدون iterrows (أسرع) ---
    for idx, row in enumerate(df.values):
        try:
            values = row

            # الاسم
            party_name = ''
            if mapping.get('party_name') is not None:
                party_name = safe_str(values[mapping['party_name']])
            if not party_name:
                continue

            # رقم الهوية / الملف
            id_number = ''
            if mapping.get('id_number') is not None:
                id_number = safe_str(values[mapping['id_number']])

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

            # نوع العملية: لازم تكون "تسجيل" أو "تحصيل" فقط، غير كدة الصف مرفوض
            if mapping.get('transaction_type') is not None:
                tx_type = safe_str(values[mapping['transaction_type']])
                if 'تسجيل' in tx_type:
                    income_type = 'registration'
                elif 'تحصيل' in tx_type:
                    income_type = 'installment'
                else:
                    errors.append(f'صف {idx+1}: نوع العملية "{tx_type}" غير صحيح (يجب أن يكون "تسجيل" أو "تحصيل")')
                    continue
            else:
                # لا يوجد عمود نوع عملية في الملف: كل الصفوف تحصيل افتراضياً
                income_type = 'installment'

            # طريقة الدفع: مدى / بنك / كاش فقط
            payment_method = 'mada'
            if mapping.get('payment_method') is not None:
                pm = safe_str(values[mapping['payment_method']]).lower()
                if 'بنك' in pm or 'تحويل' in pm or 'bank' in pm:
                    payment_method = 'bank_transfer'
                elif 'كاش' in pm or 'نقد' in pm or 'cash' in pm:
                    payment_method = 'cash'
                elif 'مدى' in pm or 'mada' in pm:
                    payment_method = 'mada'

            # مدينة
            city = ''
            if mapping.get('city') is not None:
                city = safe_str(values[mapping['city']])

            # محصل: مطلوب دائماً ولازم يكون من طاقم العمل
            collector = ''
            collected_by_user_id = None
            if mapping.get('collector_name') is not None:
                collector = safe_str(values[mapping['collector_name']])
                if not collector:
                    errors.append(f'صف {idx+1}: المحصل مطلوب')
                    continue
                found_collector_id = find_collector_id(collector, collectors_cache_branch) or \
                    find_collector_id(collector, collectors_cache_all)
                if not found_collector_id:
                    errors.append(f'صف {idx+1}: المحصل "{collector}" غير مسجل ضمن طاقم العمل')
                    continue
                collected_by_user_id = found_collector_id
            else:
                # لا يوجد عمود محصل في الملف: المستخدم الذي يقوم بالاستيراد هو المحصل الافتراضي
                collected_by_user_id = user.id if user else None
                collector = user.get_full_name() if user else ''
                if not collected_by_user_id:
                    errors.append(f'صف {idx+1}: المحصل مطلوب')
                    continue

            # رقم العملية
            tx_num = ''
            if mapping.get('transaction_number') is not None:
                tx_num = safe_str(values[mapping['transaction_number']])

            # الدورة / الدبلومة: لازم تكون مسجلة بالفعل في النظام (بدون إنشاء تلقائي)
            course_id = None
            if mapping.get('course') is not None:
                course_raw = safe_str(values[mapping['course']])
                if not course_raw:
                    errors.append(f'صف {idx+1}: لا يمكن إضافة سعر بدون إضافة دورة')
                    continue
                course_id = find_course_id(course_raw, courses_cache, always_pick_closest=True)
                if not course_id:
                    errors.append(f'صف {idx+1}: لا توجد أي دورة مسجلة في النظام لمطابقة "{course_raw}"')
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

    # الترتيب مهم: الكلمات المفتاحية الأكثر تحديداً لازم تتفحص قبل الأعم منها
    # (مثلاً "صيانة سيارات" قبل "صيانة" لوحدها) عشان متتلخبطش المطابقة
    category_map = {
        'رواتب': 'salaries',
        'إيجار': 'rent',
        'مرافق': 'utilities',
        'كهرباء': 'utilities',
        'مياه': 'utilities',
        'إنترنت': 'utilities',
        'أدوات مكتبية': 'office_supplies',
        'مكتبية': 'office_supplies',
        'مستلزمات': 'supplies',
        'تسويق': 'marketing',
        'صيانة سيارات': 'car_maintenance',
        'سيارات': 'car_maintenance',
        'صيانة': 'maintenance',
        'بنك': 'bank',
        'ضيافة': 'hospitality',
        'انتقالات': 'transportation',
        'تذاكر': 'transportation',
        'حجز': 'transportation',
        'حكومية': 'government',
        'محروقات': 'fuel',
        'بنزين': 'fuel',
        'وقود': 'fuel',
        'عمومية': 'general_admin',
        'إدارية': 'general_admin',
        'أخرى': 'other',
    }

    def find_expense_category(cat_raw):
        """يطابق الفئة بالكلمات المفتاحية أولاً، ولو مفيش تطابق يجرب أقرب فئة
        بالتشابه النصي، ولو حتى ده مفيش تطابق كافي بيسيبها لـ 'أخرى'"""
        if not cat_raw:
            return None
        for key, val in category_map.items():
            if key in cat_raw:
                return val

        import difflib
        best_ratio = 0
        best_val = None
        for value, label in Expense.EXPENSE_CATEGORY_CHOICES:
            ratio = difflib.SequenceMatcher(None, cat_raw, label).ratio()
            if ratio > best_ratio and ratio >= 0.45:
                best_ratio = ratio
                best_val = value
        return best_val

    for idx, row in enumerate(df.values):
        try:
            values = row

            description = ''
            if mapping.get('description') is not None:
                description = safe_str(values[mapping['description']])
            if not description:
                errors.append(f'صف {idx+1}: البند مطلوب')
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
                cat_raw = safe_str(values[mapping['category']])
                matched_category = find_expense_category(cat_raw)
                if matched_category:
                    category = matched_category

            receipt = ''
            if mapping.get('receipt_number') is not None:
                receipt = safe_str(values[mapping['receipt_number']])

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
