from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from datetime import date
from decimal import Decimal

from branches.models import Branch
from transactions.models import Income, Expense
from dashboard.services import get_dashboard_payload


@login_required
def dashboard(request):
    payload = get_dashboard_payload(request, request.user)
    return render(request, 'dashboard/dashboard.html', {'initial_data': payload})


@login_required
def dashboard_data_api(request):
    payload = get_dashboard_payload(request, request.user)
    return JsonResponse(payload)


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
