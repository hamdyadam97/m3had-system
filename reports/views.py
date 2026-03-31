"""
تقارير متقدمة للنظام
===================
1. تقارير المعاهد (Branches)
2. تقارير الموظفين (Employees)
3. تقارير الدورات (Courses)
4. تقارير الدبلومات (Diplomas)
5. تقارير الفترات الزمنية (Time Analysis)
6. التقارير القديمة (Daily, Monthly, etc.)
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.db.models import Count, Sum, Avg, F, Q, ExpressionWrapper, DecimalField, Func
from django.db.models.functions import TruncMonth, TruncDate, ExtractHour
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import datetime, timedelta, date
from decimal import Decimal
import pandas as pd

try:
    from weasyprint import HTML
except ImportError:
    HTML = None

from branches.models import Branch, BranchTarget
from courses.models import Course
from students.models import Student
from transactions.models import Income, Expense
from accounts.models import User


# =============================================================================
# Helpers & Mixins
# =============================================================================

def get_visible_branches(user):
    """دالة مساعدة لتحديد نطاق رؤية المستخدم"""
    if user.is_superuser or user.user_type == 'admin':
        return Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        return user.managed_branches.all()
    else:
        return Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()


def get_date_range(request):
    """استخراج نطاق التاريخ من الطلب"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = date.today().replace(day=1)  # بداية الشهر الحالي
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()
    
    return start_date, end_date


def get_branch_filter(request):
    """استخراج فلتر الفرع من الطلب"""
    branch_id = request.GET.get('branch')
    if branch_id:
        return Branch.objects.filter(id=branch_id).first()
    return None


def get_employee_filter(request):
    """استخراج فلتر الموظف من الطلب"""
    employee_id = request.GET.get('employee')
    if employee_id:
        return User.objects.filter(id=employee_id).first()
    return None


def get_course_filter(request):
    """استخراج فلتر الكورس من الطلب"""
    course_id = request.GET.get('course')
    if course_id:
        return Course.objects.filter(id=course_id).first()
    return None


# =============================================================================
# القديمة - Basic Reports
# =============================================================================

@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def reports_dashboard(request):
    """لوحة تحكم التقارير"""
    return render(request, 'reports/reports_dashboard.html')


@login_required
@permission_required('transactions.view_reports', raise_exception=True)
def daily_report(request):
    today = date.today()
    date_str = request.GET.get('date')
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today

    # تحديد الفروع المتاحة
    visible_branches = get_visible_branches(request.user)
    branch_id = request.GET.get('branch')

    if branch_id and branch_id != 'all':
        active_branches = visible_branches.filter(id=branch_id)
    else:
        active_branches = visible_branches

    # جلب البيانات
    incomes = Income.objects.filter(branch__in=active_branches, date=selected_date).select_related('student', 'course', 'collected_by')
    expenses = Expense.objects.filter(branch__in=active_branches, date=selected_date).select_related('created_by')

    # --- منطق التصدير ---
    export_type = request.GET.get('export')

    # 1. تصدير إيرادات Excel
    if export_type == 'income_excel':
        columns = {
            'student__full_name': 'اسم الطالب',
            'course__name': 'الدورة',
            'amount': 'المبلغ',
            'income_type': 'النوع',
            'payment_method': 'طريقة الدفع',
            'date': 'التاريخ'
        }
        return export_to_excel(incomes, "daily_incomes", columns)

    # 2. تصدير مصروفات Excel
    if export_type == 'expense_excel':
        columns = {
            'category': 'الفئة',
            'description': 'الوصف',
            'amount': 'المبلغ',
            'receipt_number': 'رقم الإيصال',
            'date': 'التاريخ'
        }
        return export_to_excel(expenses, "daily_expenses", columns)

    # 3. تصدير PDF
    if export_type == 'income_pdf' and HTML:
        total_sum = incomes.aggregate(Sum('amount'))['amount__sum'] or 0
        context = {
            'data': incomes,
            'title': 'تقرير الإيرادات اليومي',
            'date': selected_date,
            'type': 'income',
            'total_sum': total_sum,
            'user': request.user
        }
        return export_to_pdf(request, context, 'reports/pdf_template.html', "incomes_report")

    if export_type == 'expense_pdf' and HTML:
        total_sum = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        context = {
            'data': expenses,
            'title': 'تقرير المصروفات اليومي',
            'date': selected_date,
            'type': 'expense',
            'total_sum': total_sum,
            'user': request.user
        }
        return export_to_pdf(request, context, 'reports/pdf_template.html', "expenses_report")

    # الحسابات المجمعة
    summary = incomes.aggregate(
        total=Sum('amount'),
        reg_total=Sum('amount', filter=Q(income_type='registration')),
        ins_total=Sum('amount', filter=Q(income_type='installment'))
    )
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_income = summary['total'] or 0

    context = {
        'date': selected_date,
        'visible_branches': visible_branches,
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
    total_target = BranchTarget.objects.filter(
        branch__in=active_branches,
        year=year,
        month=month
    ).aggregate(total=Sum('amount'))['total'] or 0
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


# =============================================================================
# 1. تقارير المعاهد (Branches Reports)
# =============================================================================

@login_required
def branches_report(request):
    """
    تقرير شامل للمعاهد:
    - أكثر المعاهد عددًا من حيث الطلاب
    - أكثر المعاهد دخلًا
    - أكثر شهر تحقيقًا للدخل لكل معهد
    """
    start_date, end_date = get_date_range(request)
    
    # ===== أكثر المعاهد عددًا من حيث الطلاب =====
    branches_by_students = Branch.objects.filter(
        student__registration_date__range=[start_date, end_date]
    ).annotate(
        students_count=Count('student', distinct=True)
    ).order_by('-students_count')[:10]
    
    # ===== أكثر المعاهد دخلًا (إجمالي) =====
    # جلب الإيرادات أولاً ثم ربطها بالفروع
    income_by_branch = Income.objects.filter(
        date__range=[start_date, end_date]
    ).values('branch').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    branches_by_income_total = []
    for item in income_by_branch:
        try:
            branch = Branch.objects.get(id=item['branch'])
            branch.total_income = item['total']
            branches_by_income_total.append(branch)
        except Branch.DoesNotExist:
            pass
    
    # ===== أكثر المعاهد دخلًا (حسب الشهر) - نفس النتيجة =====
    branches_by_month = branches_by_income_total
    
    # ===== أكثر شهر تحقيقًا للدخل لكل معهد =====
    top_months_by_branch = []
    for branch in Branch.objects.all():
        top_month = Income.objects.filter(
            branch=branch,
            date__range=[start_date, end_date]
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('-total').first()
        
        if top_month:
            top_months_by_branch.append({
                'branch': branch,
                'month': top_month['month'],
                'amount': top_month['total']
            })
    
    # ترتيب حسب المبلغ
    top_months_by_branch = sorted(top_months_by_branch, key=lambda x: x['amount'], reverse=True)[:10]
    
    context = {
        'branches_by_students': branches_by_students,
        'branches_by_income_total': branches_by_income_total,
        'branches_by_month': branches_by_month,
        'top_months_by_branch': top_months_by_branch,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/branches_report.html', context)


# =============================================================================
# 2. تقارير الموظفين (Employees Reports)
# =============================================================================

@login_required
def employees_report(request):
    """
    تقرير شامل للموظفين:
    - أكثر الموظفين تسجيلًا للطلاب
    - أكثر الموظفين من حيث عدد الطلاب المسجلين
    - أكثر الموظفين إيرادات
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    
    # ===== أكثر الموظفين تسجيلًا للطلاب (عدد عمليات) =====
    emp_reg_filter = Q(income__income_type='registration', income__date__range=[start_date, end_date])
    if branch:
        emp_reg_filter &= Q(income__branch=branch)
    
    employees_by_registrations = User.objects.filter(
        emp_reg_filter
    ).annotate(
        registrations_count=Count('income', distinct=True)
    ).order_by('-registrations_count')[:10]
    
    # ===== أكثر الموظفين من حيث عدد الطلاب المسجلين (طلاب فريدين) =====
    emp_std_filter = Q(income__date__range=[start_date, end_date])
    if branch:
        emp_std_filter &= Q(income__branch=branch)
    
    employees_by_students = User.objects.filter(
        emp_std_filter
    ).annotate(
        unique_students=Count('income__student', distinct=True)
    ).order_by('-unique_students')[:10]
    
    # ===== أكثر الموظفين إيرادات =====
    income_by_employee = Income.objects.filter(
        date__range=[start_date, end_date]
    )
    if branch:
        income_by_employee = income_by_employee.filter(branch=branch)
    
    income_by_employee = income_by_employee.values('collected_by').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    employees_by_income = []
    for item in income_by_employee:
        try:
            emp = User.objects.get(id=item['collected_by'])
            emp.total_income = item['total']
            employees_by_income.append(emp)
        except User.DoesNotExist:
            pass
    
    context = {
        'employees_by_registrations': employees_by_registrations,
        'employees_by_students': employees_by_students,
        'employees_by_income': employees_by_income,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': Branch.objects.all(),
    }
    return render(request, 'reports/employees_report.html', context)


# =============================================================================
# 3. تقارير الدورات (Courses Reports)
# =============================================================================

@login_required
def courses_report(request):
    """
    تقرير شامل للدورات:
    - أكثر الدورات تسجيلًا (عدد الطلاب)
    - أكثر الدورات دخلًا
    - في معهد معين
    - في فترة زمنية معينة
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    
    # ===== أكثر الدورات تسجيلًا (عدد الطلاب) =====
    std_filter = Q(student__registration_date__range=[start_date, end_date])
    if branch:
        std_filter &= Q(student__branch=branch)
    
    courses_by_students = Course.objects.filter(
        course_type='course'
    ).filter(
        std_filter
    ).annotate(
        students_count=Count('student', distinct=True)
    ).order_by('-students_count')[:10]
    
    # ===== أكثر الدورات دخلًا =====
    income_by_course = Income.objects.filter(
        date__range=[start_date, end_date],
        course__course_type='course'
    )
    if branch:
        income_by_course = income_by_course.filter(branch=branch)
    
    income_by_course = income_by_course.values('course').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    courses_by_income = []
    for item in income_by_course:
        try:
            course = Course.objects.get(id=item['course'])
            course.total_income = item['total']
            courses_by_income.append(course)
        except Course.DoesNotExist:
            pass
    
    context = {
        'courses_by_students': courses_by_students,
        'courses_by_income': courses_by_income,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': Branch.objects.all(),
    }
    return render(request, 'reports/courses_report.html', context)


# =============================================================================
# 4. تقارير الدبلومات (Diplomas Reports)
# =============================================================================

@login_required
def diplomas_report(request):
    """
    تقرير شامل للدبلومات:
    - أكثر الدبلومات تسجيلًا
    - عدد الطلاب المسجلين في كل دبلوم
    - أكثر الدبلومات تحقيقًا للدخل
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    
    # ===== أكثر الدبلومات تسجيلًا =====
    std_filter = Q(student__registration_date__range=[start_date, end_date])
    if branch:
        std_filter &= Q(student__branch=branch)
    
    diplomas_by_students = Course.objects.filter(
        course_type='diploma'
    ).filter(
        std_filter
    ).annotate(
        students_count=Count('student', distinct=True)
    ).order_by('-students_count')[:10]
    
    # ===== أكثر الدبلومات دخلًا =====
    income_by_diploma = Income.objects.filter(
        date__range=[start_date, end_date],
        course__course_type='diploma'
    )
    if branch:
        income_by_diploma = income_by_diploma.filter(branch=branch)
    
    income_by_diploma = income_by_diploma.values('course').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    diplomas_by_income = []
    for item in income_by_diploma:
        try:
            diploma = Course.objects.get(id=item['course'])
            diploma.total_income = item['total']
            diplomas_by_income.append(diploma)
        except Course.DoesNotExist:
            pass
    
    # ===== تفاصيل كل دبلوم =====
    diplomas_detail = Course.objects.filter(course_type='diploma')
    
    context = {
        'diplomas_by_students': diplomas_by_students,
        'diplomas_by_income': diplomas_by_income,
        'diplomas_detail': diplomas_detail,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': Branch.objects.all(),
    }
    return render(request, 'reports/diplomas_report.html', context)


# =============================================================================
# 5. تقارير الفترات الزمنية (Time Analysis Reports)
# =============================================================================

@login_required
def time_analysis_report(request):
    """
    تحليل الفترات الزمنية:
    - أكثر فترات التسجيل (ساعات / أيام)
    - أكثر فترات تحقيق الدخل
    - تحليل التسجيل حسب الوقت (صباح/مساء)
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    
    # فلتر الفرع
    base_filter = Q(date__range=[start_date, end_date])
    student_filter = Q(registration_date__range=[start_date, end_date])
    if branch:
        base_filter &= Q(branch=branch)
        student_filter &= Q(branch=branch)
    
    # ===== أكثر الأيام تسجيلًا =====
    top_days = Income.objects.filter(
        base_filter
    ).annotate(
        day=TruncDate('date')
    ).values('day').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-count')[:10]
    
    # ===== أكثر الأيام دخلًا =====
    top_income_days = Income.objects.filter(
        base_filter
    ).annotate(
        day=TruncDate('date')
    ).values('day').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    # ===== أكثر الشهور تسجيلًا =====
    top_months = Income.objects.filter(
        base_filter
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-count')[:10]
    
    # ===== تحليل حسب وقت اليوم (صباح/مساء) =====
    morning_income = Income.objects.filter(
        base_filter,
        created_at__hour__lt=12
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    afternoon_income = Income.objects.filter(
        base_filter,
        created_at__hour__gte=12,
        created_at__hour__lt=17
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    evening_income = Income.objects.filter(
        base_filter,
        created_at__hour__gte=17
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    time_periods = [
        {'name': 'الصباح (6 ص - 12 ظ)', 'amount': morning_income},
        {'name': 'الفترة المسائية (12 ظ - 5 م)', 'amount': afternoon_income},
        {'name': 'المساء (5 م - 10 م)', 'amount': evening_income},
    ]
    
    context = {
        'top_days': top_days,
        'top_income_days': top_income_days,
        'top_months': top_months,
        'time_periods': time_periods,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': Branch.objects.all(),
    }
    return render(request, 'reports/time_analysis.html', context)


# =============================================================================
# KPIs & Dashboard Widgets
# =============================================================================

@login_required
def kpis_dashboard(request):
    """
    مؤشرات الأداء الرئيسية (KPIs):
    - إجمالي الطلاب
    - إجمالي الإيرادات
    - عدد التسجيلات
    - متوسط قيمة الطالب
    - أعلى معهد
    - أعلى موظف
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    
    # ===== إجمالي الطلاب =====
    std_filter = Q(registration_date__range=[start_date, end_date])
    if branch:
        std_filter &= Q(branch=branch)
    total_students = Student.objects.filter(std_filter).count()
    
    # ===== إجمالي الإيرادات =====
    inc_filter = Q(date__range=[start_date, end_date])
    if branch:
        inc_filter &= Q(branch=branch)
    total_income = Income.objects.filter(inc_filter).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # ===== عدد التسجيلات =====
    total_registrations = Income.objects.filter(
        inc_filter,
        income_type='registration'
    ).count()
    
    # ===== متوسط قيمة الطالب =====
    avg_student_value = Income.objects.filter(inc_filter).aggregate(
        avg=Avg('amount')
    )['avg'] or Decimal('0')
    
    # ===== أعلى معهد =====
    top_branch_data = Income.objects.filter(
        date__range=[start_date, end_date]
    )
    if branch:
        top_branch_data = top_branch_data.filter(branch=branch)
    
    top_branch_data = top_branch_data.values('branch').annotate(
        total=Sum('amount')
    ).order_by('-total').first()
    
    top_branch = None
    if top_branch_data:
        try:
            top_branch = Branch.objects.get(id=top_branch_data['branch'])
            top_branch.total_income = top_branch_data['total']
        except Branch.DoesNotExist:
            pass
    
    # ===== أعلى موظف =====
    top_employee_data = Income.objects.filter(
        date__range=[start_date, end_date]
    )
    if branch:
        top_employee_data = top_employee_data.filter(branch=branch)
    
    top_employee_data = top_employee_data.values('collected_by').annotate(
        total=Sum('amount')
    ).order_by('-total').first()
    
    top_employee = None
    if top_employee_data and top_employee_data['collected_by']:
        try:
            top_employee = User.objects.get(id=top_employee_data['collected_by'])
            top_employee.total_income = top_employee_data['total']
        except User.DoesNotExist:
            pass
    
    context = {
        'total_students': total_students,
        'total_income': total_income,
        'total_registrations': total_registrations,
        'avg_student_value': avg_student_value,
        'top_branch': top_branch,
        'top_employee': top_employee,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': Branch.objects.all(),
    }
    return render(request, 'reports/kpis_dashboard.html', context)


# =============================================================================
# Helper Functions for Export
# =============================================================================

def export_to_excel(queryset, filename, columns_map):
    """دالة مساعدة لتصدير Excel بالعربي"""
    # تحويل الـ Queryset إلى DataFrame
    data = list(queryset.values(*columns_map.keys()))
    df = pd.DataFrame(data)

    # إعادة تسمية الأعمدة للعربية
    df.rename(columns=columns_map, inplace=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename={filename}_{datetime.now().strftime("%Y%m%d")}.xlsx'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return response


def export_to_pdf(request, context, template_name, filename):
    """دالة مساعدة لتصدير PDF بالعربي"""
    if not HTML:
        return HttpResponse("PDF export requires WeasyPrint library", status=500)
    
    html_string = render_to_string(template_name, context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    html.write_pdf(response)
    return response
