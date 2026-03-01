from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum, Count, Q
from datetime import date, timedelta, datetime
from transactions.models import Income, Expense
from students.models import Student
from courses.models import Course
from branches.models import Branch
from django.contrib.auth import get_user_model

User = get_user_model()


def get_visible_branches(user):
    """دالة مساعدة لتحديد نطاق رؤية المستخدم"""
    if user.is_superuser or user.user_type == 'admin':
        return Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        return user.managed_branches.all()
    else:
        return Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()


@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def reports_dashboard(request):
    """لوحة تحكم التقارير"""
    return render(request, 'reports/reports_dashboard.html')


@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def daily_report(request):
    """التقرير اليومي المطور"""
    today = date.today()
    date_str = request.GET.get('date')
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today

    # اختيار فرع محدد (للأدمن والمدير الإقليمي)
    branch_id = request.GET.get('branch')
    visible_branches = get_visible_branches(request.user)

    if branch_id and branch_id != 'all':
        active_branches = visible_branches.filter(id=branch_id)
    else:
        active_branches = visible_branches

    # جلب البيانات بناءً على الفروع المتاحة
    incomes = Income.objects.filter(branch__in=active_branches, date=selected_date).select_related('branch',
                                                                                                   'collected_by')
    expenses = Expense.objects.filter(branch__in=active_branches, date=selected_date).select_related('branch')

    # الحسابات المجمعة
    summary = incomes.aggregate(
        total=Sum('amount'),
        reg_total=Sum('amount', filter=Q(income_type='registration')),
        ins_total=Sum('amount', filter=Q(income_type='installment')),
        reg_count=Count('id', filter=Q(income_type='registration')),
        ins_count=Count('id', filter=Q(income_type='installment')),
        cash=Sum('amount', filter=Q(payment_method='cash')),
        visa=Sum('amount', filter=Q(payment_method='visa')),
        bank=Sum('amount', filter=Q(payment_method='bank_transfer'))
    )

    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_income = summary['total'] or 0

    context = {
        'date': selected_date,
        'visible_branches': visible_branches,
        'selected_branch_id': branch_id,
        'incomes': incomes,
        'expenses': expenses,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_amount': total_income - total_expenses,
        'summary': summary,
    }
    return render(request, 'reports/daily_report.html', context)


@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def monthly_report(request):
    """التقرير الشهري المطور"""
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    visible_branches = get_visible_branches(request.user)
    branch_id = request.GET.get('branch')

    if branch_id and branch_id != 'all':
        active_branches = visible_branches.filter(id=branch_id)
    else:
        active_branches = visible_branches

    incomes = Income.objects.filter(branch__in=active_branches, date__range=[month_start, month_end])
    expenses = Expense.objects.filter(branch__in=active_branches, date__range=[month_start, month_end])

    total_income = incomes.aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_target = active_branches.aggregate(total=Sum('monthly_target'))['total'] or 0

    new_students = Student.objects.filter(branch__in=active_branches,
                                          registration_date__range=[month_start, month_end]).count()
    achievement_percentage = (total_income / total_target * 100) if total_target > 0 else 0

    context = {
        'year': year, 'month': month,
        'visible_branches': visible_branches,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_amount': total_income - total_expenses,
        'new_students': new_students,
        'total_target': total_target,
        'achievement_percentage': round(achievement_percentage, 2),
    }
    return render(request, 'reports/monthly_report.html', context)


@login_required
@permission_required('courses.view_course', raise_exception=True)
def courses_report(request):
    """تقرير أداء الدورات لكل الفروع المتاحة"""
    today = date.today()
    visible_branches = get_visible_branches(request.user)

    # جلب الدورات المرتبطة بالفروع المتاحة للمستخدم
    courses = Course.objects.filter(branches__in=visible_branches, is_active=True).distinct()

    courses_data = []
    for course in courses:
        data = Income.objects.filter(course=course, branch__in=visible_branches).aggregate(
            total_income=Sum('amount'),
            student_count=Count('student', distinct=True)
        )
        courses_data.append({
            'course': course,
            'total_income': data['total_income'] or 0,
            'total_registrations': data['student_count'] or 0,
        })

    return render(request, 'reports/courses_report.html', {'courses_data': courses_data})


@login_required
@permission_required('accounts.view_user', raise_exception=True)
def employees_report(request):
    """تقرير أداء الموظفين بناءً على نطاق الوصول"""
    today = date.today()
    visible_branches = get_visible_branches(request.user)

    employees = User.objects.filter(branch__in=visible_branches, is_active=True)

    employees_data = []
    for emp in employees:
        stats = Income.objects.filter(collected_by=emp, date=today).aggregate(
            total=Sum('amount'),
            reg_count=Count('id', filter=Q(income_type='registration')),
            ins_count=Count('id', filter=Q(income_type='installment'))
        )
        employees_data.append({
            'employee': emp,
            'total_collected': stats['total'] or 0,
            'registrations_count': stats['reg_count'] or 0,
            'installments_count': stats['ins_count'] or 0,
        })

    return render(request, 'reports/employees_report.html', {'employees_data': employees_data})