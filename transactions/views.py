from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Sum
from datetime import date

from branches.models import Branch
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
            # إذا لم يكن أدمن، الفرع هو فرع المستخدم الحالي
            if not request.user.is_admin():
                income.branch = request.user.branch

            income.collected_by = request.user
            income.save()
            messages.success(request, 'تم تسجيل الإيراد بنجاح!')
            return redirect('transactions:income_list')
    else:
        form = IncomeForm(user=request.user)
    return render(request, 'transactions/income_form.html', {'form': form, 'title': 'تسجيل إيراد جديد'})


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