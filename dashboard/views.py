from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from datetime import date
from branches.models import Branch
from transactions.models import Income, Expense
from students.models import Student
from courses.models import Course


@login_required
def dashboard(request):
    user = request.user
    today = date.today()
    month_start = today.replace(day=1)

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

    # 4. حساب الهدف المالي (التصحيح هنا)
    # نقوم بجمع المبالغ من موديل BranchTarget المرتبط بالفروع الظاهرة وللشهر والسنة الحالية
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

    context = {
        'branches': visible_branches,
        'today_income': today_income,
        'today_expenses': today_expenses,
        'today_net': today_income - today_expenses,
        'today_registrations': today_registrations,
        'monthly_income': monthly_income,
        'monthly_target': total_target,
        'achievement_percentage': round(achievement_percentage, 2),
        'new_students': new_students_month,
        'total_students': total_active_students,
        'is_global_view': visible_branches.count() > 1,
    }

    return render(request, 'dashboard/dashboard.html', context)

@login_required
def branch_dashboard(request, branch_id):
    user = request.user
    branch = get_object_or_404(Branch, id=branch_id)
    today = date.today()
    month_start = today.replace(day=1)

    # ... (نفس كود الـ Security Check اللي كتبناه) ...

    # 2. الإحصائيات المالية للفرع
    today_income = Income.objects.filter(branch=branch, date=today).aggregate(total=Sum('amount'))['total'] or 0
    today_expenses = Expense.objects.filter(branch=branch, date=today).aggregate(total=Sum('amount'))['total'] or 0
    monthly_income = Income.objects.filter(branch=branch, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0
    monthly_expenses = Expense.objects.filter(branch=branch, date__gte=month_start).aggregate(total=Sum('amount'))['total'] or 0

    # جلب التارجت من الموديل المرتبط (التصحيح)
    target_amount = branch.get_current_month_target() # استخدمنا الدالة اللي انت كاتبها في الموديل
    achievement_percentage = (monthly_income / target_amount * 100) if target_amount > 0 else 0

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
        'monthly_target': target_amount, # القيمة المصححة
        'achievement_percentage': round(achievement_percentage, 2),
        'top_courses': top_courses,
    }
    return render(request, 'dashboard/branch_dashboard.html', context)