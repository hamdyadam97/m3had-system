import os
import tempfile
import pandas as pd
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db.models import Q
from django.db import transaction
from datetime import datetime


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

            # نوع العملية
            tx_type = ''
            if mapping.get('transaction_type') is not None:
                tx_type = str(values[mapping['transaction_type']]).strip()

            if 'دفعه' in tx_type or 'دفعة' in tx_type or 'اخر' in tx_type:
                income_type = 'installment'
            else:
                income_type = 'registration'

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
            collected_by_user = user
            if mapping.get('collector_name') is not None:
                collector = str(values[mapping['collector_name']]).strip()
                if collector and collector in collectors_cache:
                    collected_by_user_id = collectors_cache[collector]
                else:
                    collected_by_user_id = user.id if user else None
            else:
                collected_by_user_id = user.id if user else None

            # رقم العملية
            tx_num = ''
            if mapping.get('transaction_number') is not None:
                tx_num = str(values[mapping['transaction_number']]).strip()

            # الدورة / الدبلومة (من cache)
            course_id = None
            if mapping.get('course') is not None:
                course_raw = str(values[mapping['course']]).strip()
                if course_raw:
                    for cname, cid in courses_cache.items():
                        if course_raw in cname or cname in course_raw:
                            course_id = cid
                            break

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
            Income.objects.bulk_create(income_objects, batch_size=500)

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
            Expense.objects.bulk_create(expense_objects, batch_size=500)

    return imported, errors
