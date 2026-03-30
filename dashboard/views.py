from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import Group

from branches.models import Branch
from transactions.models import Income, Expense
from students.models import Student
from students.notification_models import NotificationLog
from courses.models import Course
from accounts.models import User, Notification


@login_required
def dashboard(request):
    user = request.user
    today = date.today()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)

    # 1. تحديد الفروع المتاحة للمستخدم
    if user.is_superuser or user.user_type == 'admin':
        visible_branches = Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        visible_branches = user.managed_branches.all()
    else:
        visible_branches = Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()

    # 2. تصفية البيانات المالية
    income_qs = Income.objects.filter(branch__in=visible_branches)
    expense_qs = Expense.objects.filter(branch__in=visible_branches)
    student_qs = Student.objects.filter(branch__in=visible_branches)

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

    # إحصائيات الطلاب
    today_registrations = income_qs.filter(date=today, income_type='registration').count()
    new_students_month = student_qs.filter(registration_date__gte=month_start).count()
    total_active_students = student_qs.filter(is_active=True).count()

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
        'achievement_percentage': round(achievement_percentage, 2),
        'new_students': new_students_month,
        'total_students': total_active_students,
        'is_global_view': visible_branches.count() > 1,
    }

    # إضافة إحصائيات الأدمن
    if user.is_superuser or user.user_type == 'admin':
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
        branch_students = Student.objects.filter(branch=branch, is_active=True).count()
        
        branches_with_stats.append({
            'id': branch.id,
            'name': branch.name,
            'today_income': branch_today_income,
            'monthly_income': branch_monthly_income,
            'monthly_target': branch_target,
            'achievement': round(float(branch_achievement), 1),
            'students_count': branch_students,
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
    recent_incomes = income_qs.select_related('student', 'branch').order_by('-created_at')[:5]
    for income in recent_incomes:
        recent_activities.append({
            'type': 'income',
            'icon': 'fa-money-bill-wave',
            'title': f"{'تحصيل قسط' if income.income_type == 'installment' else 'تسجيل جديد'}",
            'description': f"{income.student.full_name} - {income.amount:,.0f} ر.س",
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
    
    # آخر الطلاب
    recent_students = student_qs.order_by('-created_at')[:3]
    for student in recent_students:
        recent_activities.append({
            'type': 'student',
            'icon': 'fa-user-graduate',
            'title': 'طالب جديد',
            'description': student.full_name,
            'time': student.created_at.strftime('%d/%m'),
        })
    
    # ترتيب النشاطات حسب الوقت
    context['recent_activities'] = sorted(recent_activities, key=lambda x: x['time'], reverse=True)[:8]

    # ====== الإشعارات ======
    # 1. الإشعارات الداخلية للمستخدم (غير مقروءة)
    unread_notifications = Notification.objects.filter(
        recipient=user,
        is_read=False
    ).order_by('-created_at')[:5]
    context['unread_notifications'] = unread_notifications
    context['unread_notifications_count'] = unread_notifications.count()
    
    # 2. سجل الإشعارات المرسلة للطلاب (آخر 5)
    recent_notification_logs = NotificationLog.objects.select_related(
        'student', 'installment'
    ).order_by('-created_at')[:5]
    context['recent_notification_logs'] = recent_notification_logs

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
        user.user_type == 'admin' or
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

    top_courses = Course.objects.filter(branches=branch).annotate(
        students_count=Count('student', filter=Q(student__branch=branch, student__is_active=True))
    ).order_by('-students_count')[:5]

    context = {
        'branch': branch,
        'today_income': today_income,
        'today_expenses': today_expenses,
        'today_net': today_income - today_expenses,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_net': monthly_income - monthly_expenses,
        'monthly_target': target_amount,
        'achievement_percentage': round(float(achievement_percentage), 1),
        'top_courses': top_courses,
    }
    return render(request, 'dashboard/branch_dashboard.html', context)
