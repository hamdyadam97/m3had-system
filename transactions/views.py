from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Sum
from datetime import date, timezone

from branches.models import Branch
from students.models import Student
from .models import Income, Expense, DailySummary
from .forms import IncomeForm, ExpenseForm
from django.core.paginator import Paginator


@login_required
@permission_required('transactions.view_income', raise_exception=True)
def income_list(request):
    """قائمة الإيرادات مع التقسيم وفلترة الفروع حسب نوع المستخدم"""

    # 1. تحسين الأداء بجلب البيانات المرتبطة
    income_queryset = Income.objects.select_related(
        'student', 'course', 'branch', 'collected_by'
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
@permission_required('transactions.add_income', raise_exception=True)
def income_add(request):
    """إضافة إيراد وتثبيت الفرع والمحصل تلقائياً"""
    if request.method == 'POST':
        form = IncomeForm(request.POST, user=request.user)

        if form.is_valid():
            income = form.save(commit=False)

            # ✅ الفرع - من الطالب أو من المستخدم
            if not income.branch_id:
                if income.student and income.student.branch:
                    income.branch = income.student.branch
                elif request.user.branch:
                    income.branch = request.user.branch
                else:
                    messages.error(request, 'خطأ: لم يتم تحديد الفرع')
                    return render(request, 'transactions/income_form.html', {
                        'form': form,
                        'title': 'تسجيل إيراد جديد'
                    })

            income.collected_by = request.user

            try:
                income.save()
                messages.success(request, 'تم تسجيل الإيراد بنجاح!')
                return redirect('transactions:income_list')
            except Exception as e:
                messages.error(request, f'خطأ في الحفظ: {str(e)}')
        else:
            messages.error(request, f'خطأ في البيانات: {form.errors}')
    else:
        form = IncomeForm(user=request.user)

    return render(request, 'transactions/income_form.html', {
        'form': form,
        'title': 'تسجيل إيراد جديد'
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


@login_required
@permission_required('transactions.add_expense', raise_exception=True)
def expense_add(request):
    """إضافة مصروف جديد"""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            if not request.user.is_admin():
                expense.branch = request.user.branch

            expense.created_by = request.user
            expense.save()
            messages.success(request, 'تم تسجيل المصروف بنجاح!')
            return redirect('transactions:expense_list')
    else:
        form = ExpenseForm(user=request.user)
    return render(request, 'transactions/expense_form.html', {'form': form, 'title': 'تسجيل مصروف جديد'})
@login_required
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


@login_required
def get_students_by_type(request):
    """جلب الطلاب حسب نوع الإيراد - يشتغل في كل الحالات"""
    income_type = request.GET.get('income_type')
    branch_id = request.GET.get('branch_id')

    if not income_type:
        return JsonResponse({'students': []})

    user = request.user

    # تحديد الفروع المتاحة للمستخدم
    if branch_id:
        # فيه فرع محدد في الطلب (صفحة إضافة إيراد)
        branches = [int(branch_id)]
    elif user.branch:
        # المستخدم عنده فرع (موظف عادي)
        branches = [user.branch.id]
    elif user.is_superuser or user.user_type == 'admin':
        # أدمن من غير فرع - نجيب كل الفروع
        from branches.models import Branch
        branches = list(Branch.objects.filter(is_active=True).values_list('id', flat=True))
    elif user.user_type == 'regional_manager':
        # مدير إقليمي
        branches = list(user.managed_branches.values_list('id', flat=True))
    else:
        return JsonResponse({'students': []})

    # جلب الطلاب من الفروع المتاحة
    base_query = Student.objects.filter(branch_id__in=branches, is_active=True)
    students = []

    for student in base_query:
        total_paid = student.get_total_paid()
        remaining = student.get_remaining_amount()

        # لو مدفوع كامل → نتخطاه
        if remaining <= 0:
            continue

        if income_type == 'registration':
            # تسجيل جديد = أول مرة يدفع
            if total_paid == 0:
                first_amount = (student.installment_amount
                                if student.payment_method == 'installment'
                                else student.total_price)

                students.append({
                    'id': student.id,
                    'name': student.full_name,
                    'branch_name': student.branch.name,  # للأدمن يعرف الفرع
                    'course_name': student.course.name if student.course else '',
                    'payment_method': student.payment_method,
                    'first_amount': float(first_amount),
                    'total_price': float(student.total_price),
                    'label': f'{student.full_name} ({student.branch.name}) - {first_amount:,.0f} ر.س' if len(
                        branches) > 1 else f'{student.full_name} - {first_amount:,.0f} ر.س',
                    'status': 'new',
                    'can_pay': True
                })

        else:  # installment
            # لازم يكون دفع قبل كده
            if total_paid == 0:
                continue

            info = student.get_next_installment_info()
            can_pay, reason = student.can_pay_installment_now(early_days_allowed=5)

            if info:
                label = student.full_name
                if len(branches) > 1:
                    label += f' ({student.branch.name})'

                if info['status'] == 'overdue':
                    label += f' - 🔴 قسط {info["installment_number"]} متأخر'
                elif info['status'] == 'due_today':
                    label += f' - ⚠️ قسط {info["installment_number"]} اليوم'
                elif info['status'] == 'due_soon':
                    label += f' - 🟡 قسط {info["installment_number"]} بعد {info["days_until"]} يوم'
                else:
                    label += f' - ⏳ قسط {info["installment_number"]} بعد {info["days_until"]} يوم'

                students.append({
                    'id': student.id,
                    'name': student.full_name,
                    'branch_name': student.branch.name,
                    'course_name': student.course.name if student.course else '',
                    'remaining_amount': float(remaining),
                    'installment_amount': float(student.installment_amount),
                    'current_installment': info['installment_number'],
                    'due_date': info['due_date'].strftime('%Y-%m-%d'),
                    'days_until': info['days_until'],
                    'status': info['status'],
                    'can_pay': can_pay,
                    'label': label,
                    'message': reason
                })

    # ترتيب: المتأخرين أولاً
    status_order = {'overdue': 0, 'due_today': 1, 'due_soon': 2, 'upcoming': 3, 'new': 4}
    students.sort(key=lambda x: status_order.get(x.get('status'), 99))

    return JsonResponse({'students': students})


@login_required
def get_student_payment_info(request):
    """جلب معلومات الدفع للطالب"""
    student_id = request.GET.get('student_id')
    income_type = request.GET.get('income_type', 'installment')

    student = get_object_or_404(Student, id=student_id)

    total_paid = student.get_total_paid()
    remaining = student.get_remaining_amount()

    # ✅ بيانات الكورس والسعر
    course = student.course
    course_data = {
        'id': course.id if course else None,
        'name': course.name if course else 'غير محدد',
        'price': float(course.price) if course and hasattr(course, 'price') else float(student.total_price),
    }

    data = {
        'type': income_type,
        'student_id': student.id,
        'student_name': student.full_name,
        'payment_method': student.payment_method,

        # ✅ بيانات الكورس
        'course': course_data,

        # ✅ بيانات المبالغ
        'total_price': float(student.total_price),
        'total_paid': float(total_paid),
        'remaining_amount': float(remaining),

        # ✅ معلومات الأقساط
        'installment_count': student.installment_count,
        'installment_amount': float(student.installment_amount) if student.installment_amount else 0,
        'paid_installments': student.paid_installments,
    }

    if income_type == 'registration':
        # أول دفعة
        if student.payment_method == 'installment':
            first_amount = student.installment_amount
            data['suggested_amount'] = float(first_amount)
            data['max_allowed'] = float(first_amount)
            data['amount_label'] = 'أول قسط'
            data['message'] = f'أول قسط: {first_amount:,.2f} ر.س (من إجمالي {student.total_price:,.2f})'
        else:
            # دفعة كاملة
            data['suggested_amount'] = float(student.total_price)
            data['max_allowed'] = float(student.total_price)
            data['amount_label'] = 'الدفعة الكاملة'
            data['message'] = f'دفعة كاملة: {student.total_price:,.2f} ر.س'

    else:  # installment
        info = student.get_next_installment_info()
        can_pay, reason = student.can_pay_installment_now(early_days_allowed=5)

        data['can_pay'] = can_pay
        data['message'] = reason

        if info:
            data['current_installment'] = {
                'number': info['installment_number'],
                'due_date': info['due_date'].strftime('%Y-%m-%d'),
                'amount': float(info['amount']),
                'status': info['status'],
            }

            if can_pay:
                data['suggested_amount'] = float(info['amount'])
                data['max_allowed'] = float(remaining)
                data['amount_label'] = f'قسط {info["installment_number"]}'

                # ✅ خيارات الدفع
                data['options'] = [
                    {
                        'type': 'current',
                        'label': f'قسط {info["installment_number"]}',
                        'amount': float(info['amount']),
                        'description': f'المستحق: {info["due_date"]}'
                    },
                    {
                        'type': 'full',
                        'label': 'تسديد كامل',
                        'amount': float(remaining),
                        'description': f'سداد المتبقي كله ({remaining:,.2f})'
                    }
                ]

                # لو نظام أقساط، نضيف خيار دفع قسطين
                if student.payment_method == 'installment' and remaining > info['amount'] * 2:
                    data['options'].insert(1, {
                        'type': 'double',
                        'label': f'قسطين ({info["installment_number"]} و {info["installment_number"] + 1})',
                        'amount': float(info['amount'] * 2),
                        'description': 'دفع قسطين مرة واحدة'
                    })
            else:
                data['suggested_amount'] = 0
                data['error'] = True

    return JsonResponse(data)