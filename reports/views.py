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
from transactions.models import Income, Expense
from accounts.models import User
from accounts.services import get_visible_branches
from courses.models import Course


# =============================================================================
# Helpers & Mixins
# =============================================================================

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
    return None


# =============================================================================
# القديمة - Basic Reports
# =============================================================================

@login_required
def charts_report(request):
    """صفحة الرسومات البيانية المتقدمة"""
    today = date.today()
    visible_branches = get_visible_branches(request.user)
    
    # === 1. إيرادات/مصروفات آخر 30 يوم ===
    last_30_days = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        day_income = Income.objects.filter(date=d, branch__in=visible_branches).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        day_expenses = Expense.objects.filter(date=d, branch__in=visible_branches).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        last_30_days.append({
            'date': d.strftime('%Y-%m-%d'),
            'income': float(day_income),
            'expenses': float(day_expenses)
        })
    
    # === 2. إيرادات/مصروفات آخر 12 شهر (SQLite-safe) ===
    last_12_months = []
    for i in range(11, -1, -1):
        # حساب الشهر المستهدف
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        
        month_income = Income.objects.filter(
            date__year=year, date__month=month, branch__in=visible_branches
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        month_expenses = Expense.objects.filter(
            date__year=year, date__month=month, branch__in=visible_branches
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        last_12_months.append({
            'label': f"{year}-{month:02d}",
            'income': float(month_income),
            'expenses': float(month_expenses)
        })
    
    # === 3. أكثر 10 فروع ===
    top_branches = []
    for item in Income.objects.filter(branch__in=visible_branches).values('branch__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]:
        top_branches.append({'branch__name': item['branch__name'], 'total': float(item['total'])})
    
    # === 4. أكثر 10 دورات ===
    top_courses = []
    for item in Income.objects.filter(branch__in=visible_branches, course__isnull=False).values('course__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]:
        top_courses.append({'course__name': item['course__name'], 'total': float(item['total'])})
    
    # === 5. أكثر 10 محصلين ===
    top_collectors_raw = Income.objects.filter(branch__in=visible_branches).values('collected_by__first_name', 'collected_by__last_name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    top_collectors = []
    for item in top_collectors_raw:
        name = f"{item['collected_by__first_name'] or ''} {item['collected_by__last_name'] or ''}".strip() or 'غير معروف'
        top_collectors.append({'name': name, 'total': float(item['total'])})
    
    # === 6. توزيع أنواع الإيرادات ===
    income_types = []
    for item in Income.objects.filter(branch__in=visible_branches).values('income_type').annotate(
        total=Sum('amount')
    ).order_by('-total'):
        label = {'registration': 'تسجيل جديد', 'installment': 'تحصيل قسط'}.get(item['income_type'], item['income_type'])
        income_types.append({'income_type': item['income_type'], 'label': label, 'total': float(item['total'])})
    
    # === 7. توزيع فئات المصروفات ===
    expense_category_labels = dict(Expense.EXPENSE_CATEGORY_CHOICES)
    expense_categories = []
    for item in Expense.objects.filter(branch__in=visible_branches).values('category').annotate(
        total=Sum('amount')
    ).order_by('-total'):
        expense_categories.append({'category': item['category'], 'label': expense_category_labels.get(item['category'], item['category']), 'total': float(item['total'])})
    
    # === 8. مقارنة الفروع - آخر 7 أيام ===
    branches_comparison = []
    branch_names = list(visible_branches.values_list('name', flat=True)[:8])
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_data = {'date': d.strftime('%Y-%m-%d')}
        for bname in branch_names:
            day_total = Income.objects.filter(date=d, branch__name=bname, branch__in=visible_branches).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            day_data[bname] = float(day_total)
        branches_comparison.append(day_data)
    
    context = {
        'last_30_days': last_30_days,
        'last_12_months': last_12_months,
        'top_branches': top_branches,
        'top_courses': top_courses,
        'top_collectors': top_collectors,
        'income_types': income_types,
        'expense_categories': expense_categories,
        'branch_names': branch_names,
        'branches_comparison': branches_comparison,
    }
    return render(request, 'reports/charts.html', context)


@login_required
def reports_dashboard(request):
    """لوحة تحكم التقارير مع Charts"""
    today = date.today()
    month_start = today.replace(day=1)
    visible_branches = get_visible_branches(request.user)
    
    # إحصائيات الشهر الحالي
    month_income = Income.objects.filter(
        date__range=[month_start, today], branch__in=visible_branches
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    month_expenses = Expense.objects.filter(
        date__range=[month_start, today], branch__in=visible_branches
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # أكثر 5 فروع
    top_branches = []
    for item in Income.objects.filter(
        date__range=[month_start, today], branch__in=visible_branches
    ).values('branch__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:5]:
        top_branches.append({'branch__name': item['branch__name'], 'total': float(item['total'])})
    
    # أكثر 5 دورات
    top_courses = []
    for item in Income.objects.filter(
        date__range=[month_start, today],
        course__isnull=False,
        branch__in=visible_branches
    ).values('course__name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:5]:
        top_courses.append({'course__name': item['course__name'], 'total': float(item['total'])})
    
    # أكثر 5 محصلين
    top_collectors_raw = Income.objects.filter(
        date__range=[month_start, today], branch__in=visible_branches
    ).values('collected_by__first_name', 'collected_by__last_name').annotate(
        total=Sum('amount')
    ).order_by('-total')[:5]
    
    top_collectors = []
    for item in top_collectors_raw:
        name = f"{item['collected_by__first_name'] or ''} {item['collected_by__last_name'] or ''}".strip() or 'غير معروف'
        top_collectors.append({'name': name, 'total': float(item['total'])})
    
    # إيرادات ومصروفات آخر 7 أيام
    last_7_days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_income = Income.objects.filter(date=d, branch__in=visible_branches).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        day_expenses = Expense.objects.filter(date=d, branch__in=visible_branches).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        last_7_days.append({
            'date': d.strftime('%Y-%m-%d'),
            'income': float(day_income),
            'expenses': float(day_expenses)
        })
    
    context = {
        'month_income': month_income,
        'month_expenses': month_expenses,
        'month_profit': month_income - month_expenses,
        'top_branches': top_branches,
        'top_courses': top_courses,
        'top_collectors': top_collectors,
        'last_7_days': last_7_days,
    }
    return render(request, 'reports/reports_dashboard.html', context)


@login_required
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
    incomes = Income.objects.filter(branch__in=active_branches, date=selected_date).select_related('collected_by')
    expenses = Expense.objects.filter(branch__in=active_branches, date=selected_date).select_related('created_by')

    # --- منطق التصدير ---
    export_type = request.GET.get('export')

    # 1. تصدير إيرادات Excel
    if export_type == 'income_excel':
        columns = {
            'party_name': 'الاسم / الجهة',
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
    new_students = 0
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
    - أكثر المعاهد مصاريف
    - أكثر شهر تحقيقًا للدخل لكل معهد
    """
    start_date, end_date = get_date_range(request)
    visible_branches = get_visible_branches(request.user)
    
    # ===== أكثر المعاهد عددًا من حيث الطلاب (فريدين) =====
    students_by_branch_qs = Income.objects.filter(
        date__range=[start_date, end_date],
        branch__in=visible_branches,
        party_name__isnull=False
    ).exclude(party_name='').values('branch').annotate(
        students_count=Count('party_name', distinct=True)
    ).order_by('-students_count')[:10]
    
    branches_by_students = []
    for item in students_by_branch_qs:
        try:
            branch = Branch.objects.get(id=item['branch'])
            branch.students_count = item['students_count']
            branches_by_students.append(branch)
        except Branch.DoesNotExist:
            pass
    
    # ===== أكثر المعاهد دخلًا (إجمالي) =====
    income_by_branch = Income.objects.filter(
        date__range=[start_date, end_date], branch__in=visible_branches
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
    
    # ===== أكثر المعاهد مصاريف (إجمالي) =====
    expenses_by_branch = Expense.objects.filter(
        date__range=[start_date, end_date], branch__in=visible_branches
    ).values('branch').annotate(
        total_expenses=Sum('amount')
    ).order_by('-total_expenses')[:10]
    
    branches_by_expenses = []
    for item in expenses_by_branch:
        try:
            branch = Branch.objects.get(id=item['branch'])
            branch.total_expenses = item['total_expenses']
            branches_by_expenses.append(branch)
        except Branch.DoesNotExist:
            pass
    
    # ===== أكثر شهر تحقيقًا للدخل لكل معهد =====
    top_months_by_branch = []
    for branch in visible_branches:
        top_month = Income.objects.filter(
            branch=branch,
            date__range=[start_date, end_date]
        ).values('date__year', 'date__month').annotate(
            total=Sum('amount')
        ).order_by('-total').first()
        
        if top_month:
            top_months_by_branch.append({
                'branch': branch,
                'month': date(top_month['date__year'], top_month['date__month'], 1),
                'amount': top_month['total']
            })
    
    # ترتيب حسب المبلغ
    top_months_by_branch = sorted(top_months_by_branch, key=lambda x: x['amount'], reverse=True)[:10]
    
    # ===== أكثر يوم تحقيقًا للدخل لكل معهد =====
    top_days_by_branch = []
    for branch in visible_branches:
        top_day = Income.objects.filter(
            branch=branch,
            date__range=[start_date, end_date]
        ).values('date').annotate(
            total=Sum('amount')
        ).order_by('-total').first()
        
        if top_day:
            top_days_by_branch.append({
                'branch': branch,
                'day': top_day['date'],
                'amount': top_day['total']
            })
    
    top_days_by_branch = sorted(top_days_by_branch, key=lambda x: x['amount'], reverse=True)[:10]
    
    context = {
        'branches_by_students': branches_by_students,
        'branches_by_income_total': branches_by_income_total,
        'branches_by_expenses': branches_by_expenses,
        'top_months_by_branch': top_months_by_branch,
        'top_days_by_branch': top_days_by_branch,
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
    تقرير شامل للمحصلين:
    - أكثر المحصلين تسجيلًا جديدًا (عدد + مبلغ)
    - أكثر المحصلين تحصيل أقساط (عدد + مبلغ)
    - أكثر المحصلين إيرادات (إجمالي)
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    visible_branches = get_visible_branches(request.user)
    
    def build_employee_list(queryset, count_field, amount_field):
        """مساعد لبناء قائمة موظفين من queryset"""
        result = []
        for item in queryset:
            if item['collected_by']:
                try:
                    emp = User.objects.get(id=item['collected_by'])
                    setattr(emp, count_field, item.get(count_field, 0))
                    setattr(emp, amount_field, item.get(amount_field, 0))
                    result.append(emp)
                except User.DoesNotExist:
                    pass
        return result
    
    # ===== أكثر المحصلين تسجيلًا جديدًا =====
    reg_qs = Income.objects.filter(
        income_type='registration',
        date__range=[start_date, end_date],
        branch__in=visible_branches
    )
    if branch and branch in visible_branches:
        reg_qs = reg_qs.filter(branch=branch)
    
    reg_data = reg_qs.values('collected_by').annotate(
        reg_count=Count('id'),
        reg_amount=Sum('amount')
    ).order_by('-reg_count')[:10]
    employees_by_registrations = build_employee_list(reg_data, 'reg_count', 'reg_amount')
    
    # ===== أكثر المحصلين أقساطًا =====
    ins_qs = Income.objects.filter(
        income_type='installment',
        date__range=[start_date, end_date],
        branch__in=visible_branches
    )
    if branch and branch in visible_branches:
        ins_qs = ins_qs.filter(branch=branch)
    
    ins_data = ins_qs.values('collected_by').annotate(
        ins_count=Count('id'),
        ins_amount=Sum('amount')
    ).order_by('-ins_count')[:10]
    employees_by_installments = build_employee_list(ins_data, 'ins_count', 'ins_amount')
    
    # ===== أكثر المحصلين إيرادات (إجمالي) =====
    total_qs = Income.objects.filter(
        date__range=[start_date, end_date],
        branch__in=visible_branches
    )
    if branch and branch in visible_branches:
        total_qs = total_qs.filter(branch=branch)
    
    total_data = total_qs.values('collected_by').annotate(
        total_income=Sum('amount')
    ).order_by('-total_income')[:10]
    employees_by_income = build_employee_list(total_data, 'total_income_count', 'total_income')
    
    context = {
        'employees_by_registrations': employees_by_registrations,
        'employees_by_installments': employees_by_installments,
        'employees_by_income': employees_by_income,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': visible_branches,
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
    - الأقساط المحصلة لكل دورة
    """
    start_date, end_date = get_date_range(request)
    branch = get_branch_filter(request)
    visible_branches = get_visible_branches(request.user)
    
    base_filter = Q(date__range=[start_date, end_date], branch__in=visible_branches)
    if branch and branch in visible_branches:
        base_filter &= Q(branch=branch)
    
    # ===== أكثر الدورات تسجيلًا (طلاب فريدين) =====
    courses_by_students_qs = Income.objects.filter(
        base_filter, course__isnull=False
    ).values('course').annotate(
        students_count=Count('party_name', distinct=True)
    ).order_by('-students_count')[:10]
    
    courses_by_students = []
    for item in courses_by_students_qs:
        try:
            course = Course.objects.get(id=item['course'])
            course.students_count = item['students_count']
            courses_by_students.append(course)
        except Course.DoesNotExist:
            pass
    
    # ===== أكثر الدورات دخلًا =====
    courses_by_income_qs = Income.objects.filter(
        base_filter, course__isnull=False
    ).values('course').annotate(
        total_income=Sum('amount')
    ).order_by('-total_income')[:10]
    
    courses_by_income = []
    for item in courses_by_income_qs:
        try:
            course = Course.objects.get(id=item['course'])
            course.total_income = item['total_income']
            courses_by_income.append(course)
        except Course.DoesNotExist:
            pass
    
    # ===== الأقساط المحصلة لكل دورة =====
    installment_courses_qs = Income.objects.filter(
        base_filter, income_type='installment', course__isnull=False
    ).values('course').annotate(
        installment_count=Count('id'),
        total_installments=Sum('amount')
    ).order_by('-total_installments')[:10]
    
    installment_courses = []
    for item in installment_courses_qs:
        try:
            course = Course.objects.get(id=item['course'])
            course.installment_count = item['installment_count']
            course.total_installments = item['total_installments']
            installment_courses.append(course)
        except Course.DoesNotExist:
            pass
    
    context = {
        'courses_by_students': courses_by_students,
        'courses_by_income': courses_by_income,
        'installment_courses': installment_courses,
        'start_date': start_date,
        'end_date': end_date,
        'selected_branch': branch,
        'branches': visible_branches,
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
    
    diplomas_by_students = []
    diplomas_by_income = []
    diplomas_detail = []
    
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
    if branch:
        base_filter &= Q(branch=branch)
    
    # ===== أكثر الأيام تسجيلًا =====
    top_days = Income.objects.filter(
        base_filter
    ).values('date').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-count')[:10]
    
    # ===== أكثر الأيام دخلًا =====
    top_income_days = Income.objects.filter(
        base_filter
    ).values('date').annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]
    
    # ===== أكثر الشهور تسجيلًا =====
    top_months_raw = Income.objects.filter(
        base_filter
    ).values('date__year', 'date__month').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-count')[:10]
    
    top_months = []
    for item in top_months_raw:
        top_months.append({
            'month': date(item['date__year'], item['date__month'], 1),
            'count': item['count'],
            'total': item['total'],
        })
    
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
    total_students = 0
    
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
