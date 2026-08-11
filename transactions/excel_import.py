import os
import glob
import json
import secrets
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


def _match_quality(ratio):
    if ratio >= 0.85:
        return 'exact'
    if ratio >= 0.6:
        return 'fuzzy'
    return 'low_confidence'


def match_course(course_raw, courses_cache):
    """زي find_course_id بس بيرجع معاها (id, جودة التطابق, اسم الدورة اللي
    اتحددت) عشان تتعرض للمستخدم في شاشة المعاينة يتأكد منها قبل الاعتماد."""
    cleaned_raw = clean_course_name(course_raw)
    if not cleaned_raw:
        return None, None, None

    for cname, cid in courses_cache.items():
        if cleaned_raw == clean_course_name(cname):
            return cid, 'exact', cname

    for cname, cid in courses_cache.items():
        cleaned_cname = clean_course_name(cname)
        if cleaned_raw in cleaned_cname or cleaned_cname in cleaned_raw:
            return cid, 'exact', cname

    import difflib
    best_ratio = 0
    best_id = None
    best_name = None
    for cname, cid in courses_cache.items():
        ratio = difflib.SequenceMatcher(None, cleaned_raw, clean_course_name(cname)).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = cid
            best_name = cname

    if best_id is None:
        return None, None, None
    return best_id, _match_quality(best_ratio), best_name


# الترتيب مهم: الكلمات المفتاحية الأكثر تحديداً لازم تتفحص قبل الأعم منها
# (مثلاً "صيانة سيارات" قبل "صيانة" لوحدها) عشان متتلخبطش المطابقة
EXPENSE_CATEGORY_MAP = {
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


def match_expense_category(cat_raw, category_choices):
    """يطابق الفئة بالكلمات المفتاحية أولاً، ولو مفيش تطابق يجرب أقرب فئة
    بالتشابه النصي، ولو حتى ده مفيش تطابق كافي بيرجع 'أخرى'. بيرجع دايماً
    (قيمة الفئة, جودة التطابق, الاسم المعروض) عشان تتعرض للمستخدم."""
    choices_dict = dict(category_choices)
    cat_raw = (cat_raw or '').strip()
    if not cat_raw:
        return 'other', None, None

    # القيمة ممكن تكون أصلاً المفتاح الداخلي (مثلاً 'utilities') لو جاية من
    # <select> بعد إعادة تحقق سابقة، مش نص عربي خام من الملف
    if cat_raw in choices_dict:
        return cat_raw, 'exact', choices_dict[cat_raw]

    for key, val in EXPENSE_CATEGORY_MAP.items():
        if key in cat_raw:
            return val, 'exact', choices_dict.get(val, val)

    import difflib
    best_ratio = 0
    best_val = None
    best_label = None
    for value, label in category_choices:
        ratio = difflib.SequenceMatcher(None, cat_raw, label).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_val = value
            best_label = label

    if best_val and best_ratio >= 0.45:
        return best_val, _match_quality(best_ratio), best_label
    return 'other', 'low_confidence', choices_dict.get('other', 'أخرى')


def _build_collectors_cache(qs):
    cache = {}
    for u in qs.values('id', 'first_name', 'last_name', 'username'):
        cache[u['username']] = u['id']
        full = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip()
        if full:
            cache[full] = u['id']
    return cache


def _parse_amount(raw):
    try:
        val = str(raw).replace(',', '').strip()
        if not val:
            return None
        amount = float(val)
        return amount if amount > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_date_field(raw):
    """يرجع (نص التاريخ بصيغة ISO, رسالة خطأ أو None). خانة فاضية = تاريخ
    النهاردة بدون خطأ. نص متعرفش نفسّره كتاريخ = خطأ."""
    raw = (raw or '').strip()
    if not raw:
        return timezone.now().date().isoformat(), None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date().isoformat(), None
    except ValueError:
        pass
    parsed = detect_date_format(raw)
    if parsed:
        return parsed.isoformat(), None
    return raw, 'تاريخ غير صالح'


def _resolve_income_type(raw):
    raw = (raw or '').strip()
    if raw in ('registration', 'installment'):
        return raw, None
    if not raw:
        return 'installment', None
    if 'تسجيل' in raw:
        return 'registration', None
    if 'تحصيل' in raw:
        return 'installment', None
    return raw, f'نوع العملية "{raw}" غير صحيح (يجب أن يكون "تسجيل" أو "تحصيل")'


def _resolve_payment_method(raw):
    raw = (raw or '').strip()
    if raw in ('mada', 'visa', 'mastercard', 'bank_transfer', 'cash'):
        return raw
    low = raw.lower()
    if 'بنك' in low or 'تحويل' in low or 'bank' in low:
        return 'bank_transfer'
    if 'كاش' in low or 'نقد' in low or 'cash' in low:
        return 'cash'
    if 'فيزا' in low or 'visa' in low:
        return 'visa'
    if 'ماستر' in low or 'master' in low:
        return 'mastercard'
    return 'mada'


INCOME_FIELDS = [
    'party_name', 'id_number', 'amount', 'date', 'income_type', 'payment_method',
    'city', 'collector_name', 'transaction_number', 'course', 'notes',
]

EXPENSE_FIELDS = ['description', 'category', 'amount', 'date', 'receipt_number', 'notes']


def _extract_row_dict(row, mapping, fields):
    """يحول صف Excel خام (من df.values) لـ dict بأسماء حقول (مش أرقام أعمدة)،
    كل القيم نصوص، مع تحويل خلايا التاريخ الحقيقية لنص ISO فوراً.

    لو عمود معين فاضي تماماً في كل صفوف الملف، بندا/openpyxl بيتجاهلوه عند
    القراءة فيرجع df بعدد أعمدة أقل من المتوقع - فبنتعامل مع رقم عمود خارج
    الحدود كخانة فاضية بدل ما نطلع IndexError.
    """
    data = {}
    row_len = len(row)
    for field in fields:
        col = mapping.get(field)
        if col is None or col >= row_len:
            data[field] = ''
            continue
        val = row[col]
        if pd.isna(val):
            data[field] = ''
        elif field == 'date' and isinstance(val, datetime):
            data[field] = val.date().isoformat()
        else:
            data[field] = str(val).strip()
    return data


def parse_rows_for_preview(file_path, mapping, fields):
    """يقرأ الملف الخام ويحوله لقائمة dicts بأسماء حقول، جاهزة للتحقق والعرض
    في شاشة المعاينة. بيتجاهل الصفوف الفاضية تماماً بس بيسيب أي صف فيه بيانات
    جزئية (زي اسم فاضي) عشان يظهر كخطأ في المعاينة بدل ما يختفي بصمت."""
    df = pd.read_excel(file_path, header=None)
    rows = []
    for row in df.values:
        data = _extract_row_dict(row, mapping, fields)
        if any(v for v in data.values()):
            rows.append(data)
    return rows


# =============================================================================
# التحقق (Validation) - بدون أي كتابة على قاعدة البيانات
# =============================================================================

def validate_income_row(data, courses_cache, collectors_cache_branch, collectors_cache_all, course_required):
    """يتحقق من صف إيراد واحد (dict بأسماء حقول) بدون أي كتابة على قاعدة
    البيانات. نفس الدالة تُستخدم لأول توليد للمعاينة ولكل إعادة تحقق، عشان
    الاتنين ميختلفوش عن بعض أبداً."""
    errors = {}
    normalized = {}

    party_name = (data.get('party_name') or '').strip()
    normalized['party_name'] = party_name
    if not party_name:
        errors['party_name'] = 'الاسم / الجهة مطلوب'

    normalized['id_number'] = (data.get('id_number') or '').strip()

    amount = _parse_amount(data.get('amount'))
    if amount is None:
        errors['amount'] = 'مبلغ غير صالح'
        normalized['amount'] = str(data.get('amount') or '')
    else:
        normalized['amount'] = amount

    date_iso, date_err = _parse_date_field(data.get('date'))
    normalized['date'] = date_iso
    if date_err:
        errors['date'] = date_err

    income_type, type_err = _resolve_income_type(data.get('income_type'))
    normalized['income_type'] = income_type
    if type_err:
        errors['income_type'] = type_err

    normalized['payment_method'] = _resolve_payment_method(data.get('payment_method'))

    normalized['city'] = (data.get('city') or '').strip()

    collector = (data.get('collector_name') or '').strip()
    normalized['collector_name'] = collector
    collected_by_id = None
    if not collector:
        errors['collector_name'] = 'المحصل مطلوب'
    else:
        collected_by_id = find_collector_id(collector, collectors_cache_branch) or \
            find_collector_id(collector, collectors_cache_all)
        if not collected_by_id:
            errors['collector_name'] = f'المحصل "{collector}" غير مسجل ضمن طاقم العمل'

    normalized['transaction_number'] = (data.get('transaction_number') or '').strip()

    course_raw = (data.get('course') or '').strip()
    normalized['course'] = course_raw
    course_match = None
    course_id = None
    if course_raw:
        course_id, quality, resolved_name = match_course(course_raw, courses_cache)
        course_match = {'quality': quality, 'resolved_name': resolved_name}
    elif course_required:
        errors['course'] = 'لا يمكن إضافة سعر بدون إضافة دورة'

    normalized['notes'] = (data.get('notes') or '').strip()

    return normalized, errors, collected_by_id, course_id, course_match


def run_income_validation(rows, branch, course_required=True):
    """يشغّل التحقق الكامل (100% من الصفوف) على قائمة صفوف إيراد. تُستخدم في
    أول توليد للمعاينة وفي كل نداء لإعادة التحقق."""
    from courses.models import Course
    from accounts.models import User

    courses_cache = {c['name']: c['id'] for c in Course.objects.filter(is_active=True).values('id', 'name')}
    staff_qs = User.objects.filter(is_active=True, user_type__in=['employee', 'branch_manager', 'accountant'])
    collectors_cache_branch = _build_collectors_cache(staff_qs.filter(branch=branch))
    collectors_cache_all = _build_collectors_cache(staff_qs)

    results = []
    for idx, row_data in enumerate(rows):
        normalized, errors, collected_by_id, course_id, course_match = validate_income_row(
            row_data, courses_cache, collectors_cache_branch, collectors_cache_all, course_required
        )
        results.append({
            'row_number': idx + 1,
            'data': normalized,
            'errors': errors,
            'is_valid': len(errors) == 0,
            'course_match': course_match,
            'collected_by_id': collected_by_id,
            'course_id': course_id,
        })
    return results


def validate_expense_row(data, category_choices):
    """يتحقق من صف مصروف واحد (dict بأسماء حقول) بدون أي كتابة على قاعدة
    البيانات."""
    errors = {}
    normalized = {}

    description = (data.get('description') or '').strip()
    normalized['description'] = description
    if not description:
        errors['description'] = 'البند مطلوب'

    amount = _parse_amount(data.get('amount'))
    if amount is None:
        errors['amount'] = 'مبلغ غير صالح'
        normalized['amount'] = str(data.get('amount') or '')
    else:
        normalized['amount'] = amount

    date_iso, date_err = _parse_date_field(data.get('date'))
    normalized['date'] = date_iso
    if date_err:
        errors['date'] = date_err

    cat_raw = (data.get('category') or '').strip()
    category, quality, resolved_label = match_expense_category(cat_raw, category_choices)
    normalized['category'] = category
    category_match = {'quality': quality, 'resolved_name': resolved_label} if cat_raw else None

    normalized['receipt_number'] = (data.get('receipt_number') or '').strip()
    normalized['notes'] = (data.get('notes') or '').strip()

    return normalized, errors, category_match


def run_expense_validation(rows):
    """يشغّل التحقق الكامل (100% من الصفوف) على قائمة صفوف مصروف."""
    from .models import Expense
    category_choices = Expense.EXPENSE_CATEGORY_CHOICES

    results = []
    for idx, row_data in enumerate(rows):
        normalized, errors, category_match = validate_expense_row(row_data, category_choices)
        results.append({
            'row_number': idx + 1,
            'data': normalized,
            'errors': errors,
            'is_valid': len(errors) == 0,
            'category_match': category_match,
        })
    return results


# =============================================================================
# الإنشاء الفعلي (يُستخدم فقط بعد التحقق الكامل عند الاعتماد النهائي)
# =============================================================================

def create_income_records(validated_rows, branch, user):
    from .models import Income

    income_objects = []
    for row in validated_rows:
        d = row['data']
        extra_notes = []
        if d.get('notes'):
            extra_notes.append(d['notes'])
        if d.get('city'):
            extra_notes.append(f"المدينة: {d['city']}")

        income_objects.append(Income(
            branch=branch,
            date=datetime.strptime(d['date'], '%Y-%m-%d').date(),
            income_type=d['income_type'],
            amount=d['amount'],
            payment_method=d['payment_method'],
            payment_location='in_person',
            collected_by_id=row.get('collected_by_id'),
            party_name=d['party_name'],
            id_number=d.get('id_number', ''),
            collector_name=d.get('collector_name', ''),
            transaction_number=d.get('transaction_number', ''),
            course_id=row.get('course_id'),
            notes='\n'.join(extra_notes),
        ))

    with transaction.atomic():
        created = Income.objects.bulk_create(income_objects, batch_size=500)
        logger.info(f"[Excel Import] User={user} | Branch={branch} | Created={len(created)}")
    return len(created)


def create_expense_records(validated_rows, branch, user):
    from .models import Expense

    expense_objects = []
    for row in validated_rows:
        d = row['data']
        expense_objects.append(Expense(
            branch=branch,
            date=datetime.strptime(d['date'], '%Y-%m-%d').date(),
            category=d['category'],
            description=d['description'],
            amount=d['amount'],
            receipt_number=d.get('receipt_number', ''),
            notes=d.get('notes', ''),
            created_by=user,
        ))

    with transaction.atomic():
        created = Expense.objects.bulk_create(expense_objects, batch_size=500)
        logger.info(f"[Excel Expense Import] User={user} | Branch={branch} | Created={len(created)}")
    return len(created)


# =============================================================================
# تخزين مرحلي (Staging) بين خطوة المعاينة وإعادة التحقق والاعتماد النهائي
# =============================================================================

def _stage_file_path(token):
    return os.path.join(tempfile.gettempdir(), f'excel_stage_{token}.json')


def save_staged_import(kind, branch_id, owner_user_id, rows, course_required=None):
    """kind: 'income' أو 'expense'. بيرجع token غير قابل للتخمين يُستخدم بعد
    كده في إعادة التحقق والاعتماد النهائي، ولازم يفضل سري لأنه بيدي صلاحية
    كتابة على قاعدة البيانات."""
    token = secrets.token_urlsafe(24)
    payload = {
        'kind': kind,
        'owner_user_id': owner_user_id,
        'branch_id': branch_id,
        'course_required': course_required,
        'rows': rows,
    }
    with open(_stage_file_path(token), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    return token


def load_staged_import(token):
    path = _stage_file_path(token)
    if not token or not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def update_staged_rows(token, rows):
    payload = load_staged_import(token)
    if payload is None:
        return None
    payload['rows'] = rows
    with open(_stage_file_path(token), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    return payload


def delete_staged_import(token):
    try:
        os.remove(_stage_file_path(token))
    except OSError:
        pass


def cleanup_stale_staged_imports(max_age_hours=24):
    """تنضيف أفضل-محاولة لملفات معاينة مهجورة (المستخدم رفع ملف وماكملش)."""
    cutoff = timezone.now().timestamp() - max_age_hours * 3600
    pattern = os.path.join(tempfile.gettempdir(), 'excel_stage_*.json')
    for path in glob.glob(pattern):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


# =============================================================================
# دوال قديمة محفوظة للتوافق الخلفي (لسه بيستخدمها transactions/tasks.py رغم
# إنها مش متصلة بأي مسار فعلي في الواجهة حالياً) - بتفوّض داخلياً لنفس منطق
# التحقق والإنشاء الجديد بدل ما تكرره
# =============================================================================

def import_excel_data(file_path, mapping, branch, user):
    """استيراد مباشر قديم (بدون معاينة/تعديل) - محفوظة للتوافق الخلفي فقط."""
    rows = parse_rows_for_preview(file_path, mapping, INCOME_FIELDS)
    course_required = mapping.get('course') is not None
    results = run_income_validation(rows, branch, course_required=course_required)

    valid_rows = [r for r in results if r['is_valid']]
    errors = [
        f"صف {r['row_number']}: {list(r['errors'].values())[0]}"
        for r in results if not r['is_valid']
    ]
    imported = create_income_records(valid_rows, branch, user) if valid_rows else 0
    return imported, errors


def import_excel_expense_data(file_path, mapping, branch, user):
    """استيراد مباشر قديم (بدون معاينة/تعديل) - محفوظة للتوافق الخلفي فقط."""
    rows = parse_rows_for_preview(file_path, mapping, EXPENSE_FIELDS)
    results = run_expense_validation(rows)

    valid_rows = [r for r in results if r['is_valid']]
    errors = [
        f"صف {r['row_number']}: {list(r['errors'].values())[0]}"
        for r in results if not r['is_valid']
    ]
    imported = create_expense_records(valid_rows, branch, user) if valid_rows else 0
    return imported, errors
