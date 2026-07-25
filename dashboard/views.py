from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import Group

from branches.models import Branch
from transactions.models import Income, Expense
from accounts.models import User


@login_required
def dashboard(request):
    user = request.user
    today = date.today()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)

    # 1. تحديد الفروع المتاحة للمستخدم
    if user.is_superuser or user.is_admin():
        visible_branches = Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        visible_branches = user.managed_branches.all()
    else:
        visible_branches = Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()

    # 2. تصفية البيانات المالية
    income_qs = Income.objects.filter(branch__in=visible_branches)
    expense_qs = Expense.objects.filter(branch__in=visible_branches)

    # 3. حساب الإحصائيات المالية
    today_income = income_qs.filter(date=today).aggregate(total=Sum('amount'))['total'] or 0
    today_expenses = expense_qs.filter(date=today).aggregate(total=Sum('amount'))['total'] or 0
    monthly_income = income_qs.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0
    monthly_expenses = expense_qs.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0

    # 4. حساب الهدف المالي
    from branches.models import BranchTarget
    total_target = BranchTarget.objects.filter(
        branch__in=visible_branches,
        year=today.year,
        month=today.month
    ).aggregate(total=Sum('amount'))['total'] or 0

    # حساب نسبة الإنجاز
    achievement_percentage = (monthly_income / total_target * 100) if total_target > 0 else 0
    achievement_percentage_float = round(float(achievement_percentage), 2)
    achievement_width = min(int(achievement_percentage_float), 100)

    # إحصائيات التسجيلات
    today_registrations = income_qs.filter(date=today, income_type='registration').count()

    # إحصائيات الطلاب (من التسجيلات لأن مفيش students model منفصل)
    new_students = income_qs.filter(
        date__gte=month_start,
        income_type='registration',
        party_name__isnull=False
    ).exclude(party_name='').count()
    
    total_students = income_qs.filter(
        income_type='registration',
        party_name__isnull=False
    ).exclude(party_name='').values('party_name').distinct().count()

    # ====== إحصائيات إضافية للأدمن ======
    context = {
        'branches': visible_branches,
        'today_income': today_income,
        'today_expenses': today_expenses,
        'today_net': today_income - today_expenses,
        'today_registrations': today_registrations,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_target': total_target,
        'achievement_percentage': achievement_percentage_float,
        'achievement_width': achievement_width,
        'new_students': new_students,
        'total_students': total_students,
        'is_global_view': visible_branches.count() > 1,
    }

    # إضافة إحصائيات الأدمن
    if user.is_superuser or user.is_admin():
        from courses.models import Course
        context.update({
            'total_branches': Branch.objects.filter(is_active=True).count(),
            'total_users': User.objects.filter(is_active=True).count(),
            'total_courses': Course.objects.filter(is_active=True).count(),
            'total_income_month': monthly_income,
            'total_expense_month': monthly_expenses,
        })

    # بيانات الفروع مع الإحصائيات
    branches_with_stats = []
    for branch in visible_branches:
        branch_today_income = Income.objects.filter(branch=branch, date=today).aggregate(total=Sum('amount'))['total'] or 0
        branch_monthly_income = Income.objects.filter(branch=branch, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0
        branch_target = Decimal(str(branch.get_current_month_target() or 0))
        branch_achievement = (branch_monthly_income / branch_target * 100) if branch_target > 0 else 0
        
        branch_new_students = Income.objects.filter(
            branch=branch,
            date__gte=month_start,
            income_type='registration',
            party_name__isnull=False
        ).exclude(party_name='').count()
        
        branch_total_students = Income.objects.filter(
            branch=branch,
            income_type='registration',
            party_name__isnull=False
        ).exclude(party_name='').values('party_name').distinct().count()
        
        branches_with_stats.append({
            'id': branch.id,
            'name': branch.name,
            'today_income': branch_today_income,
            'monthly_income': branch_monthly_income,
            'monthly_target': branch_target,
            'achievement': round(float(branch_achievement), 1),
            'achievement_width': min(int(round(float(branch_achievement), 0)), 100),
            'students_count': branch_total_students,
            'new_students': branch_new_students,
        })
    
    context['branches_with_stats'] = branches_with_stats

    # بيانات الرسم البياني (آخر 7 أيام)
    chart_labels = []
    chart_income = []
    chart_expense = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_income = income_qs.filter(date=day).aggregate(total=Sum('amount'))['total'] or 0
        day_expense = expense_qs.filter(date=day).aggregate(total=Sum('amount'))['total'] or 0
        
        chart_labels.append(day.strftime('%d/%m'))
        chart_income.append(float(day_income))
        chart_expense.append(float(day_expense))
    
    context['chart_labels'] = chart_labels
    context['chart_income'] = chart_income
    context['chart_expense'] = chart_expense

    # آخر النشاطات
    recent_activities = []
    
    # آخر الإيرادات
    recent_incomes = income_qs.select_related('branch').order_by('-created_at')[:5]
    for income in recent_incomes:
        recent_activities.append({
            'type': 'income',
            'icon': 'fa-money-bill-wave',
            'title': f"{'تحصيل قسط' if income.income_type == 'installment' else 'تسجيل جديد'}",
            'description': f"{income.party_name} - {income.amount:,.0f} ر.س",
            'time': income.created_at.strftime('%H:%M'),
        })
    
    # آخر المصروفات
    recent_expenses = expense_qs.select_related('branch').order_by('-created_at')[:3]
    for expense in recent_expenses:
        recent_activities.append({
            'type': 'expense',
            'icon': 'fa-wallet',
            'title': expense.get_category_display(),
            'description': f"{expense.description[:30]}... - {expense.amount:,.0f} ر.س",
            'time': expense.created_at.strftime('%H:%M'),
        })
    
    # ترتيب النشاطات حسب الوقت
    context['recent_activities'] = sorted(recent_activities, key=lambda x: x['time'], reverse=True)[:8]


    return render(request, 'dashboard/dashboard.html', context)


@login_required
def branch_dashboard(request, branch_id):
    user = request.user
    branch = get_object_or_404(Branch, id=branch_id)
    today = date.today()
    month_start = today.replace(day=1)

    # Security Check
    can_view = (
        user.is_superuser or 
        user.is_admin() or
        (user.user_type == 'regional_manager' and branch in user.managed_branches.all()) or
        user.branch == branch
    )
    
    if not can_view:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    # الإحصائيات المالية
    today_income = Income.objects.filter(branch=branch, date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    today_expenses = Expense.objects.filter(branch=branch, date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    monthly_income = Income.objects.filter(branch=branch, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    monthly_expenses = Expense.objects.filter(branch=branch, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # جلب التارجت وتحويله لـ Decimal
    target_amount = Decimal(str(branch.get_current_month_target() or 0))

    # حساب نسبة الإنجاز
    if target_amount > 0:
        achievement_percentage = (monthly_income / target_amount) * 100
    else:
        achievement_percentage = 0

    achievement_percentage_float = round(float(achievement_percentage), 1)
    achievement_width = min(int(achievement_percentage_float), 100)
    
    context = {
        'branch': branch,
        'today_income': today_income,
        'today_expenses': today_expenses,
        'today_net': today_income - today_expenses,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_net': monthly_income - monthly_expenses,
        'monthly_target': target_amount,
        'achievement_percentage': achievement_percentage_float,
        'achievement_width': achievement_width,
        'top_courses': [],
    }
    return render(request, 'dashboard/branch_dashboard.html', context)
