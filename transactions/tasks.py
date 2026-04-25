import os
from celery import shared_task
from django.db import transaction
from .excel_import import import_excel_data, import_excel_expense_data


@shared_task(bind=True)
def import_income_excel_task(self, file_path, mapping, branch_id, user_id):
    """
    Task لاستيراد إيرادات من Excel في الخلفية
    """
    from branches.models import Branch
    from accounts.models import User

    branch = Branch.objects.get(id=branch_id)
    user = User.objects.get(id=user_id)

    try:
        imported, errors = import_excel_data(file_path, mapping, branch, user)
        # مسح الملف بعد الاستيراد
        try:
            os.remove(file_path)
        except:
            pass

        return {
            'status': 'success',
            'imported': imported,
            'errors': errors,
        }
    except Exception as e:
        try:
            os.remove(file_path)
        except:
            pass
        return {
            'status': 'error',
            'message': str(e),
        }


@shared_task(bind=True)
def import_expense_excel_task(self, file_path, mapping, branch_id, user_id):
    """
    Task لاستيراد مصروفات من Excel في الخلفية
    """
    from branches.models import Branch
    from accounts.models import User

    branch = Branch.objects.get(id=branch_id)
    user = User.objects.get(id=user_id)

    try:
        imported, errors = import_excel_expense_data(file_path, mapping, branch, user)
        try:
            os.remove(file_path)
        except:
            pass

        return {
            'status': 'success',
            'imported': imported,
            'errors': errors,
        }
    except Exception as e:
        try:
            os.remove(file_path)
        except:
            pass
        return {
            'status': 'error',
            'message': str(e),
        }
