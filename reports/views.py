from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum, Count, Q
from datetime import date, timedelta, datetime
from transactions.models import Income, Expense
from students.models import Student
from courses.models import Course
from branches.models import Branch, BranchTarget
from django.contrib.auth import get_user_model
import pandas as pd
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML

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
    today = date.today()
    date_str = request.GET.get('date')
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today

    # تحديد الفروع المتاحة (بناءً على دالة get_visible_branches السابقة)
    visible_branches = get_visible_branches(request.user)
    branch_id = request.GET.get('branch')

    if branch_id and branch_id != 'all':
        active_branches = visible_branches.filter(id=branch_id)
    else:
        active_branches = visible_branches

    # جلب البيانات
    incomes = Income.objects.filter(branch__in=active_branches, date=selected_date).select_related('student', 'course',
                                                                                                   'collected_by')
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

    # 3. تصدير إيرادات PDF

        # 3. تصدير إيرادات PDF
    if export_type == 'income_pdf':
            total_sum = incomes.aggregate(Sum('amount'))['amount__sum'] or 0  # حساب الإجمالي هنا
            context = {
                'data': incomes,
                'title': 'تقرير الإيرادات اليومي',
                'date': selected_date,
                'type': 'income',
                'total_sum': total_sum,  # نبعته للملف
                'user': request.user
            }
            return export_to_pdf(request, context, 'reports/pdf_template.html', "incomes_report")

        # 4. تصدير مصروفات PDF
    if export_type == 'expense_pdf':
            total_sum = expenses.aggregate(Sum('amount'))['amount__sum'] or 0  # حساب الإجمالي هنا
            context = {
                'data': expenses,
                'title': 'تقرير المصروفات اليومي',
                'date': selected_date,
                'type': 'expense',
                'total_sum': total_sum,  # نبعته للملف
                'user': request.user
            }
            return export_to_pdf(request, context, 'reports/pdf_template.html', "expenses_report")

    # الحسابات المجمعة للعرض في الصفحة
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


@login_required
@permission_required('courses.view_course', raise_exception=True)
def courses_report(request):
    """تقرير أداء الدورات مع إحصائيات زمنية وتصدير"""
    today = date.today()
    date_str = request.GET.get('date')
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today

    # تحديد بداية ونهاية الشهر للتاريخ المختار
    month_start = selected_date.replace(day=1)
    # الحصول على آخر يوم في الشهر
    next_month = selected_date.replace(day=28) + timedelta(days=4)
    month_end = next_month - timedelta(days=next_month.day)

    visible_branches = get_visible_branches(request.user)
    courses = Course.objects.filter(branches__in=visible_branches, is_active=True).distinct()

    courses_data = []
    for course in courses:
        # إحصائيات إجمالية
        total_data = Income.objects.filter(course=course, branch__in=visible_branches).aggregate(
            total_income=Sum('amount'),
            student_count=Count('student', distinct=True)
        )
        # إحصائيات يومية (للتاريخ المختار)
        daily_data = Income.objects.filter(course=course, branch__in=visible_branches, date=selected_date).aggregate(
            income=Sum('amount'),
            count=Count('id', filter=Q(income_type='registration'))
        )
        # إحصائيات شهرية (للشهر المختار)
        monthly_data = Income.objects.filter(course=course, branch__in=visible_branches,
                                             date__range=[month_start, month_end]).aggregate(
            income=Sum('amount')
        )

        courses_data.append({
            'course': course,
            'daily_registrations': daily_data['count'] or 0,
            'daily_income': daily_data['income'] or 0,
            'monthly_income': monthly_data['income'] or 0,
            'total_registrations': total_data['student_count'] or 0,
            'total_income': total_data['total_income'] or 0,
        })

    # --- منطق التصدير ---
    export_type = request.GET.get('export')
    if export_type == 'excel':
        excel_list = []
        for d in courses_data:
            excel_list.append({
                'اسم الدورة': d['course'].name,
                'النوع': d['course'].get_course_type_display(),
                'السعر': d['course'].price,
                'تسجيلات اليوم': d['daily_registrations'],
                'إيراد اليوم': d['daily_income'],
                'إيراد الشهر': d['monthly_income'],
                'إجمالي التسجيلات': d['total_registrations'],
                'إجمالي الإيرادات': d['total_income'],
            })
        df = pd.DataFrame(excel_list)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=courses_report_{selected_date}.xlsx'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return response

    if export_type == 'pdf':
        context = {
            'courses_data': courses_data,
            'title': 'تقرير أداء الدورات والدبلومات',
            'date': selected_date,
            'user': request.user,
            'type': 'courses'
        }
        return export_to_pdf(request, context, 'reports/pdf_template.html', "courses_report")

    return render(request, 'reports/courses_report.html', {
        'courses_data': courses_data,
        'date': selected_date
    })

@login_required
@permission_required('accounts.view_user', raise_exception=True)
def employees_report(request):
    """تقرير أداء الموظفين خلال فترة زمنية مع التصدير"""
    # 1. جلب التواريخ من الطلب (Default: اليوم)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    today = date.today()
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today

    visible_branches = get_visible_branches(request.user)
    employees = User.objects.filter(branch__in=visible_branches, is_active=True)

    employees_data = []
    for emp in employees:
        # فلترة الإيرادات بناءً على الموظف والفترة الزمنية
        stats = Income.objects.filter(
            collected_by=emp,
            date__range=[start_date, end_date]
        ).aggregate(
            total=Sum('amount'),
            reg_count=Count('id', filter=Q(income_type='registration')),
            ins_count=Count('id', filter=Q(income_type='installment')),
            cash=Sum('amount', filter=Q(payment_method='cash')),
            visa=Sum('amount', filter=Q(payment_method='visa')),
            bank=Sum('amount', filter=Q(payment_method='bank_transfer'))
        )

        employees_data.append({
            'employee': emp,
            'total_collected': stats['total'] or 0,
            'registrations_count': stats['reg_count'] or 0,
            'installments_count': stats['ins_count'] or 0,
            'cash_collected': stats['cash'] or 0,
            'visa_collected': stats['visa'] or 0,
            'bank_collected': stats['bank'] or 0,
        })

    # --- منطق التصدير ---
    export_type = request.GET.get('export')

    if export_type == 'excel':
        # تجهيز البيانات للإكسيل
        excel_data = []
        for d in employees_data:
            excel_data.append({
                'الموظف': d['employee'].get_full_name() or d['employee'].username,
                'التسجيلات': d['registrations_count'],
                'التحصيلات': d['installments_count'],
                'كاش': d['cash_collected'],
                'فيزا': d['visa_collected'],
                'بنك': d['bank_collected'],
                'الإجمالي': d['total_collected']
            })
        df = pd.DataFrame(excel_data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=employees_report_{start_date}.xlsx'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return response

    if export_type == 'pdf':
        context = {
            'employees_data': employees_data,
            'title': 'تقرير أداء الموظفين التفصيلي',
            'start_date': start_date,
            'end_date': end_date,
            'user': request.user,
            'type': 'employees'  # لتمييز القالب
        }
        return export_to_pdf(request, context, 'reports/pdf_template.html', "employees_report")

    context = {
        'employees_data': employees_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/employees_report.html', context)


# --- دالة مساعدة لتصدير Excel بالعربي ---
def export_to_excel(queryset, filename, columns_map):
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


# --- دالة مساعدة لتصدير PDF بالعربي ---
def export_to_pdf(request, context, template_name, filename):
    html_string = render_to_string(template_name, context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    # استخدام الخطوط المتوفرة في النظام لدعم العربي (مثل DejaVu Sans)
    html.write_pdf(response)
    return response