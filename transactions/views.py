import logging
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Sum, Q
from datetime import date
from django.utils import timezone

logger = logging.getLogger(__name__)

from branches.models import Branch
from .models import Income, Expense, DailySummary
from .forms import (
    IncomeForm, ExpenseForm,
    ExcelStyleTransactionFormSet, ExcelStyleExpenseFormSet,
    ExcelExpenseImportForm, ExcelExpenseMappingForm,
)
from django.core.paginator import Paginator
@login_required
@permission_required('transactions.view_income', raise_exception=True)
def income_list(request):
    """قائمة الإيرادات مع التقسيم وفلترة الفروع حسب نوع المستخدم"""

    # 1. تحسين الأداء بجلب البيانات المرتبطة
    income_queryset = Income.objects.select_related(
        'branch', 'collected_by'
    ).all().order_by('-date', '-created_at')

    # 2. فلترة البيانات بناءً على الرتبة (Scope)
    user = request.user

    if user.is_superuser or user.user_type == 'admin':
        # الأدمن يرى كل شيء (لا نطبق فلتر)
        pass

    elif user.user_type == 'regional_manager':
        # المدير الإقليمي يرى فقط فروع مجموعته
        income_queryset = income_queryset.filter(branch__in=user.managed_branches.all())

    else:
        # مدير الفرع والمحاسب والموظف يرون فرعهم المسجل فقط
        if user.branch:
            income_queryset = income_queryset.filter(branch=user.branch)
        else:
            # لو موظف معندوش فرع، م يشوفش حاجة (أمان زيادة)
            income_queryset = income_queryset.none()

    # 3. إعداد التقسيم (Pagination)
    paginator = Paginator(income_queryset, 20)
    page_number = request.GET.get('page')
    incomes = paginator.get_page(page_number)

    return render(request, 'transactions/income_list.html', {'incomes': incomes})


@login_required
@permission_required('transactions.view_income', raise_exception=True)
def student_list(request):
    """قائمة الطلاب المسجلين مع الدورات/الدبلومات (مجمعة بالاسم)"""

    qs = Income.objects.select_related(
        'branch', 'course', 'collected_by'
    ).filter(
        party_name__isnull=False
    ).exclude(party_name='')

    user = request.user

    if user.is_superuser or user.user_type == 'admin':
        pass
    elif user.user_type == 'regional_manager':
        qs = qs.filter(branch__in=user.managed_branches.all())
    else:
        qs = qs.filter(branch=user.branch) if user.branch else qs.none()

    # فلتر اختياري بالاسم
    search = request.GET.get('q')
    if search:
        qs = qs.filter(party_name__icontains=search)

    # فلتر اختياري بالدورة
    course_id = request.GET.get('course')
    if course_id:
        qs = qs.filter(course_id=course_id)

    # جلب كل الأسماء المميزة (pagination على الأسماء مش على الـ records)
    all_names = qs.values_list('party_name', flat=True).distinct().order_by('party_name')

    paginator = Paginator(list(all_names), 20)
    page_number = request.GET.get('page')
    page_names = paginator.get_page(page_number)

    # جلب كل الـ records للأسماء في الصفحة الحالية
    records = qs.filter(party_name__in=page_names).order_by('party_name', '-date')

    # تجميع البيانات بالاسم
    from collections import defaultdict
    students_map = defaultdict(lambda: {'courses': [], 'branches': [], 'total': 0, 'dates': [], 'records': []})
    for r in records:
        entry = students_map[r.party_name]
        entry['records'].append(r)
        if r.course and r.course not in entry['courses']:
            entry['courses'].append(r.course)
        if r.branch not in entry['branches']:
            entry['branches'].append(r.branch)
        entry['total'] += r.amount
        entry['dates'].append(r.date)

    # ترتيب النتيجة حسب ترتيب الأسماء في الصفحة
    students_list = []
    for name in page_names:
        if name in students_map:
            s = students_map[name]
            students_list.append({
                'name': name,
                'courses': s['courses'],
                'branches': s['branches'],
                'total': s['total'],
                'last_date': max(s['dates']),
                'count': len(s['records']),
            })

    # جلب الدورات للفلتر
    from courses.models import Course
    if user.is_superuser or user.user_type == 'admin':
        courses = Course.objects.all()
    elif user.user_type == 'regional_manager':
        courses = Course.objects.filter(branch__in=user.managed_branches.all())
    else:
        courses = Course.objects.filter(branch=user.branch) if user.branch else Course.objects.none()

    return render(request, 'transactions/student_list.html', {
        'students_list': students_list,
        'students': page_names,  # للـ pagination template
        'courses': courses,
        'search': search or '',
        'course_id': course_id or '',
    })



@login_required
@permission_required('transactions.view_income', raise_exception=True)
def income_detail(request, pk):
    """تفاصيل الإيراد مع حماية الخصوصية"""
    income = get_object_or_404(Income, pk=pk)
    user = request.user

    # حماية: هل للمستخدم الحق في رؤية بيانات هذا الفرع؟
    can_view = user.is_admin() or \
               (user.user_type == 'regional_manager' and income.branch in user.managed_branches.all()) or \
               (user.branch == income.branch)
    if not can_view:
        raise PermissionDenied

    return render(request, 'transactions/income_detail.html', {'income': income})


@login_required
@permission_required('transactions.add_income', raise_exception=True)
def income_add(request):
    """إضافة إيراد جديد"""
    if request.method == 'POST':
        form = IncomeForm(request.POST, user=request.user)
        if form.is_valid():
            income = form.save(commit=False)
            if not request.user.is_admin():
                income.branch = request.user.branch
            income.collected_by = income.collected_by or request.user
            if income.collected_by:
                income.collector_name = income.collected_by.get_full_name() or income.collected_by.username
            income.save()
            messages.success(request, 'تم تسجيل الإيراد بنجاح!')
            return redirect('transactions:income_list')
    else:
        form = IncomeForm(user=request.user)
    return render(request, 'transactions/income_form.html', {'form': form, 'title': 'تسجيل إيراد جديد'})


@login_required
@permission_required('transactions.view_expense', raise_exception=True)
def expense_list(request):
    """قائمة المصروفات بفلترة ذكية"""
    user = request.user
    expense_queryset = Expense.objects.select_related('branch', 'created_by').all().order_by('-date', '-created_at')

    if user.is_superuser or user.user_type == 'admin':
        pass
    elif user.user_type == 'regional_manager':
        expense_queryset = expense_queryset.filter(branch__in=user.managed_branches.all())
    else:
        expense_queryset = expense_queryset.filter(branch=user.branch) if user.branch else expense_queryset.none()

    paginator = Paginator(expense_queryset, 15)
    expenses = paginator.get_page(request.GET.get('page'))
    return render(request, 'transactions/expense_list.html', {'expenses': expenses})
def expense_detail(request, pk):
    """تفاصيل المصروف"""
    expense = get_object_or_404(Expense, pk=pk)

    # التحقق من الصلاحيات
    if not request.user.is_superuser and request.user.branch != expense.branch:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    return render(request, 'transactions/expense_detail.html', {'expense': expense})


@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def daily_summary(request):
    """ملخص مالي يومي حسب الفروع المتاحة للمستخدم"""
    user = request.user
    today = date.today()

    # تحديد الفروع المرئية
    if user.is_admin():
        branches = Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        branches = user.managed_branches.all()
    else:
        branches = Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()

    # حسابات اليوم للفروع المتاحة
    income_data = Income.objects.filter(branch__in=branches, date=today)
    expense_data = Expense.objects.filter(branch__in=branches, date=today)

    total_income = income_data.aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = expense_data.aggregate(total=Sum('amount'))['total'] or 0

    reg_income = income_data.filter(income_type='registration').aggregate(total=Sum('amount'))['total'] or 0
    ins_income = income_data.filter(income_type='installment').aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'date': today,
        'branches': branches,
        'today_income': total_income,
        'today_expenses': total_expenses,
        'today_net': total_income - total_expenses,
        'registration_income': reg_income,
        'installment_income': ins_income,
        'is_multi_branch': branches.count() > 1,
    }

    return render(request, 'transactions/daily_summary.html', context)


from django.db import transaction


@login_required
@permission_required('transactions.add_income', raise_exception=True)
def excel_style_transaction(request):
    """تسجيل مجموعة حركات مالية بنفس أسلوب ملف الـ Excel"""
    if request.method == 'POST':
        print("=" * 50)
        print("POST Data Received")
        print("=" * 50)

        formset = ExcelStyleTransactionFormSet(request.POST, user=request.user)
        print(f"Total Forms Submitted: {request.POST.get('form-TOTAL_FORMS')}")

        if formset.is_valid():
            print("Formset IS VALID - Processing save...")
            with transaction.atomic():
                count = 0
                for form in formset:
                    if not form.cleaned_data:
                        continue
                    data = form.cleaned_data
                    branch = data['branch']
                    tx_type = data['transaction_type']
                    if tx_type in ('registration', 'registration_fees', 'full_payment', 'full_fees'):
                        income_type = 'registration'
                    else:
                        income_type = 'installment'

                    payment_method = data.get('payment_method') or 'mada'

                    extra_notes = []
                    if data.get('registration_date'):
                        extra_notes.append(f"تاريخ التسجيل: {data['registration_date']}")
                    if data.get('city'):
                        extra_notes.append(f"المدينة: {data['city']}")
                    if data.get('notes'):
                        extra_notes.append(data['notes'])
                    full_notes = '\n'.join(extra_notes)
                    # تحديد المحصل
                    collected_by = data.get('collected_by') or request.user
                    collector_name = collected_by.get_full_name() if collected_by else ''
                    
                    Income.objects.create(
                        branch=branch,
                        date=data['date'],
                        income_type=income_type,
                        amount=data['amount'],
                        payment_method=payment_method,
                        payment_location='in_person',
                        collected_by=collected_by,
                        course=data.get('course'),
                        party_name=data['party_name'],
                        id_number=data.get('id_number', ''),
                        collector_name=collector_name,
                        transaction_number=data.get('transaction_number', ''),
                        notes=full_notes,
                    )
                    count += 1

                messages.success(
                    request,
                    f'تم تسجيل {count} حركة مالية بنجاح!'
                )
                return redirect('transactions:excel_style_transaction')
        else:
            # 🔴 هنا بنطبع كل الأخطاء في الـ Console
            print("\n" + "❌ FORMSSET NOT VALID!" + "\n")
            print("Non-form errors:", formset.non_form_errors())
            print("\n--- Errors per form ---")
            for i, form in enumerate(formset):
                if form.errors:
                    print(f"\nForm [{i}] errors:")
                    for field, errors in form.errors.items():
                        print(f"  Field '{field}': {errors}")
                if form.non_field_errors():
                    print(f"  Non-field errors: {form.non_field_errors()}")
            print("\n" + "=" * 50 + "\n")

            # 🔴 نبعت رسالة للمستخدم في الـ Frontend
            messages.error(request, 'يوجد أخطاء في البيانات المدخلة، يرجى مراجعة الحقول المطلوبة (باللون الأحمر)')

            # 🔴 دي أهم حاجة - لازم نرجع الـ formset بالأخطاء للـ template
            return render(request, 'transactions/excel_style_transaction.html', {
                'formset': formset,
                'title': 'تسجيل حركات مالية (أسلوب Excel)',
            })
    else:
        formset = ExcelStyleTransactionFormSet(user=request.user)

    return render(request, 'transactions/excel_style_transaction.html', {
        'formset': formset,
        'title': 'تسجيل حركات مالية (أسلوب Excel)',
    })

import os
import tempfile
from .forms import ExcelImportForm, ExcelMappingForm
from .excel_import import parse_excel_preview, import_excel_data, import_excel_expense_data


@login_required
@permission_required('transactions.add_income', raise_exception=True)
def excel_import(request):
    """استيراد ملف Excel للإيرادات"""
    if request.method == 'POST':
        step = request.POST.get('step', 'upload')

        if step == 'upload':
            form = ExcelImportForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                excel_file = form.cleaned_data['excel_file']
                branch = form.cleaned_data['branch']

                # حفظ الملف مؤقتاً
                ext = os.path.splitext(excel_file.name)[1]
                temp_name = f'excel_import_{request.user.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}{ext}'
                temp_path = os.path.join(tempfile.gettempdir(), temp_name)

                with open(temp_path, 'wb+') as dest:
                    for chunk in excel_file.chunks():
                        dest.write(chunk)

                try:
                    preview_rows, cols = parse_excel_preview(temp_path)
                except ValueError as e:
                    messages.error(request, str(e))
                    return render(request, 'transactions/excel_import.html', {
                        'form': form,
                        'title': 'استيراد من Excel',
                    })

                # تقدير افتراضي للـ mapping
                initial_mapping = {
                    'party_name': 0,
                    'id_number': 1,
                    'payment_method': 2,
                    'amount': 4,
                    'date': 5,
                    'transaction_type': 7,
                    'city': 8,
                    'collector_name': 9,
                    'transaction_number': 10,
                    'course': 11,
                }

                mapping_form = ExcelMappingForm(initial={
                    'temp_file': temp_path,
                    'branch': branch.id,
                    'step': 'import',
                    **initial_mapping
                })

                return render(request, 'transactions/excel_import.html', {
                    'form': form,
                    'mapping_form': mapping_form,
                    'preview_rows': preview_rows,
                    'title': 'استيراد من Excel - تأكيد الأعمدة',
                    'step': 'mapping',
                })

        elif step == 'import':
            mapping_form = ExcelMappingForm(request.POST)
            if mapping_form.is_valid():
                temp_path = mapping_form.cleaned_data['temp_file']
                branch = mapping_form.cleaned_data['branch']
                mapping = {
                    'party_name': mapping_form.cleaned_data.get('party_name'),
                    'id_number': mapping_form.cleaned_data.get('id_number'),
                    'payment_method': mapping_form.cleaned_data.get('payment_method'),
                    'amount': mapping_form.cleaned_data['amount'],
                    'date': mapping_form.cleaned_data['date'],
                    'transaction_type': mapping_form.cleaned_data.get('transaction_type'),
                    'city': mapping_form.cleaned_data.get('city'),
                    'collector_name': mapping_form.cleaned_data.get('collector_name'),
                    'transaction_number': mapping_form.cleaned_data.get('transaction_number'),
                    'course': mapping_form.cleaned_data.get('course'),
                    'notes': mapping_form.cleaned_data.get('notes'),
                }

                if not os.path.exists(temp_path):
                    messages.error(request, 'الملف المؤقت غير موجود، يرجى إعادة رفع الملف.')
                    return redirect('transactions:excel_import')

                # تشغيل الاستيراد في الخلفية (Celery)
                from .tasks import import_income_excel_task
                task = import_income_excel_task.delay(temp_path, mapping, branch.id, request.user.id)
                request.session['last_import_task_id'] = task.id
                messages.info(request, 'جاري استيراد الملف في الخلفية... يمكنك متابعة عملك وسيظهر الإشعار عند الانتهاء.')
                return redirect('transactions:import_task_status', task_id=task.id)
    else:
        form = ExcelImportForm(user=request.user)

    return render(request, 'transactions/excel_import.html', {
        'form': form,
        'title': 'استيراد من Excel',
        'step': 'upload',
    })


@login_required
def import_task_status(request, task_id):
    """صفحة متابعة حالة استيراد Excel في الخلفية"""
    from celery.result import AsyncResult
    from .tasks import import_income_excel_task

    task = AsyncResult(task_id)
    context = {
        'task_id': task_id,
        'task_status': task.status,
        'task_result': task.result if task.ready() else None,
    }
    return render(request, 'transactions/import_task_status.html', context)


@login_required
def task_status_api(request, task_id):
    """API JSON لمعرفة حالة Task"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    return JsonResponse({
        'task_id': task_id,
        'status': task.status,
        'ready': task.ready(),
        'result': task.result if task.ready() and isinstance(task.result, dict) else None,
    })


@login_required
@permission_required('transactions.add_expense', raise_exception=True)
def excel_style_expense(request):
    """تسجيل مجموعة مصروفات بنفس أسلوب ملف الـ Excel"""
    if request.method == 'POST':
        formset = ExcelStyleExpenseFormSet(request.POST, request.FILES, user=request.user)
        if formset.is_valid():
            with transaction.atomic():
                count = 0
                for form in formset:
                    if not form.cleaned_data:
                        continue
                    data = form.cleaned_data
                    Expense.objects.create(
                        branch=data['branch'],
                        date=data['date'],
                        category=data['category'],
                        description=data['description'],
                        amount=data['amount'],
                        receipt_number=data.get('receipt_number', ''),
                        notes=data.get('notes', ''),
                        receipt_image=data.get('receipt_image'),
                        created_by=request.user,
                    )
                    count += 1

                messages.success(
                    request,
                    f'تم تسجيل {count} مصروف بنجاح!'
                )
                return redirect('transactions:excel_style_expense')
    else:
        formset = ExcelStyleExpenseFormSet(user=request.user)

    return render(request, 'transactions/excel_style_expense.html', {
        'formset': formset,
        'title': 'تسجيل مصروفات (أسلوب Excel)',
    })


@login_required
@permission_required('transactions.add_expense', raise_exception=True)
def excel_import_expense(request):
    """استيراد ملف Excel للمصروفات"""
    if request.method == 'POST':
        step = request.POST.get('step', 'upload')

        if step == 'upload':
            form = ExcelExpenseImportForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                excel_file = form.cleaned_data['excel_file']
                branch = form.cleaned_data['branch']

                ext = os.path.splitext(excel_file.name)[1]
                temp_name = f'excel_expense_import_{request.user.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}{ext}'
                temp_path = os.path.join(tempfile.gettempdir(), temp_name)

                with open(temp_path, 'wb+') as dest:
                    for chunk in excel_file.chunks():
                        dest.write(chunk)

                try:
                    preview_rows, cols = parse_excel_preview(temp_path)
                except ValueError as e:
                    messages.error(request, str(e))
                    return render(request, 'transactions/excel_import_expense.html', {
                        'form': form,
                        'title': 'استيراد مصروفات من Excel',
                    })

                initial_mapping = {
                    'description': 0,
                    'category': 1,
                    'amount': 3,
                    'date': 4,
                    'receipt_number': 5,
                    'notes': 6,
                }

                mapping_form = ExcelExpenseMappingForm(initial={
                    'temp_file': temp_path,
                    'branch': branch.id,
                    'step': 'import',
                    **initial_mapping
                })

                return render(request, 'transactions/excel_import_expense.html', {
                    'form': form,
                    'mapping_form': mapping_form,
                    'preview_rows': preview_rows,
                    'title': 'استيراد مصروفات من Excel - تأكيد الأعمدة',
                    'step': 'mapping',
                })

        elif step == 'import':
            mapping_form = ExcelExpenseMappingForm(request.POST)
            if mapping_form.is_valid():
                temp_path = mapping_form.cleaned_data['temp_file']
                branch = mapping_form.cleaned_data['branch']
                mapping = {
                    'description': mapping_form.cleaned_data.get('description'),
                    'category': mapping_form.cleaned_data.get('category'),
                    'amount': mapping_form.cleaned_data['amount'],
                    'date': mapping_form.cleaned_data['date'],
                    'receipt_number': mapping_form.cleaned_data.get('receipt_number'),
                    'notes': mapping_form.cleaned_data.get('notes'),
                }

                if not os.path.exists(temp_path):
                    messages.error(request, 'الملف المؤقت غير موجود، يرجى إعادة رفع الملف.')
                    return redirect('transactions:excel_import_expense')

                # تشغيل الاستيراد في الخلفية (Celery)
                from .tasks import import_expense_excel_task
                task = import_expense_excel_task.delay(temp_path, mapping, branch.id, request.user.id)
                request.session['last_import_task_id'] = task.id
                messages.info(request, 'جاري استيراد المصروفات في الخلفية... يمكنك متابعة عملك.')
                return redirect('transactions:import_task_status', task_id=task.id)
    else:
        form = ExcelExpenseImportForm(user=request.user)

    return render(request, 'transactions/excel_import_expense.html', {
        'form': form,
        'title': 'استيراد مصروفات من Excel',
        'step': 'upload',
    })
