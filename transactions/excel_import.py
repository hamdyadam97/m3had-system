import os
import tempfile
import pandas as pd
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
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
    """استيراد بيانات من Excel حسب الـ mapping
    
    mapping: dict {
        'party_name': col_index or None,
        'payment_method': col_index or None,
        'amount': col_index,
        'date': col_index,
        'transaction_type': col_index or None,
        'city': col_index or None,
        'collector_name': col_index or None,
        'transaction_number': col_index or None,
        'notes': col_index or None,
    }
    """
    from .models import Income
    from branches.models import Branch

    df = pd.read_excel(file_path, header=None)
    imported = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            values = row.fillna('').tolist()

            # الاسم
            party_name = ''
            if mapping.get('party_name') is not None:
                party_name = str(values[mapping['party_name']]).strip()
            if not party_name:
                continue  # نتخطى الصفوف الفاضية

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

            # محصل
            collector = ''
            if mapping.get('collector_name') is not None:
                collector = str(values[mapping['collector_name']]).strip()

            # رقم العملية
            tx_num = ''
            if mapping.get('transaction_number') is not None:
                tx_num = str(values[mapping['transaction_number']]).strip()

            # ملاحظات إضافية
            extra_notes = []
            if mapping.get('notes') is not None:
                note_val = values[mapping['notes']]
                if pd.notna(note_val) and str(note_val).strip():
                    extra_notes.append(str(note_val).strip())
            if city:
                extra_notes.append(f"المدينة: {city}")

            Income.objects.create(
                branch=branch,
                date=date_val,
                income_type=income_type,
                amount=amount,
                payment_method=payment_method,
                payment_location='in_person',
                collected_by=user,
                party_name=party_name,
                collector_name=collector,
                transaction_number=tx_num,
                notes='\n'.join(extra_notes),
            )
            imported += 1

        except Exception as e:
            errors.append(f'صف {idx+1}: {str(e)}')

    return imported, errors


def import_excel_expense_data(file_path, mapping, branch, user):
    """استيراد بيانات المصروفات من Excel حسب الـ mapping
    
    mapping: dict {
        'description': col_index or None,
        'category': col_index or None,
        'amount': col_index,
        'date': col_index,
        'receipt_number': col_index or None,
        'notes': col_index or None,
    }
    """
    from .models import Expense
    from branches.models import Branch

    df = pd.read_excel(file_path, header=None)
    imported = 0
    errors = []

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

    for idx, row in df.iterrows():
        try:
            values = row.fillna('').tolist()

            # الوصف
            description = ''
            if mapping.get('description') is not None:
                description = str(values[mapping['description']]).strip()
            if not description:
                continue  # نتخطى الصفوف الفاضية

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

            # الفئة
            category = 'other'
            if mapping.get('category') is not None:
                cat_raw = str(values[mapping['category']]).strip()
                for key, val in category_map.items():
                    if key in cat_raw:
                        category = val
                        break

            # رقم الإيصال
            receipt = ''
            if mapping.get('receipt_number') is not None:
                receipt = str(values[mapping['receipt_number']]).strip()

            # ملاحظات
            notes = ''
            if mapping.get('notes') is not None:
                note_val = values[mapping['notes']]
                if pd.notna(note_val) and str(note_val).strip():
                    notes = str(note_val).strip()

            Expense.objects.create(
                branch=branch,
                date=date_val,
                category=category,
                description=description,
                amount=amount,
                receipt_number=receipt,
                notes=notes,
                created_by=user,
            )
            imported += 1

        except Exception as e:
            errors.append(f'صف {idx+1}: {str(e)}')

    return imported, errors
