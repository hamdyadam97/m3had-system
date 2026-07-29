"""
منطق فلترة وحساب بيانات لوحة التحكم التحليلية.

نقطة الدخول الوحيدة المستخدمة من الـ views هي get_dashboard_payload، وهي
تُستدعى من صفحة العرض الأولى (SSR) ومن الـ API (AJAX) بنفس الشكل بالضبط
حتى تتطابق البيانات في الحالتين دائماً.
"""
from datetime import date, datetime
from calendar import monthrange

from django.db.models import Sum, Count, Q, Exists, OuterRef, F
from django.db.models.functions import TruncMonth

from accounts.models import User
from accounts.services import get_visible_branches
from branches.models import Branch, BranchTarget
from courses.models import Course
from transactions.models import Income, Expense


CHART_DAILY_THRESHOLD_DAYS = 45
TOP_N = 10
RECENT_ACTIVITIES_LIMIT = 8
RECENT_ACTIVITIES_PER_TYPE = 15


# =============================================================================
# 1. حل الفلاتر (Filters resolution)
# =============================================================================

def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _resolve_branch(request, user):
    """يرجع (visible_branches_qs, can_switch_branch, selected_branch|None)."""
    visible_branches = get_visible_branches(user)
    can_switch_branch = user.is_superuser or user.is_admin() or user.user_type == 'regional_manager'

    requested_branch_id = _parse_int(request.GET.get('branch'))
    selected_branch = None
    if requested_branch_id is not None:
        # لا نثق بالفرع القادم من العميل: لازم يكون ضمن الفروع المرئية لهذا المستخدم
        selected_branch = visible_branches.filter(id=requested_branch_id).first()

    if not can_switch_branch:
        # موظف/محاسب/مدير فرع: مُثبّت على فرعه دايماً بغض النظر عن أي باراميتر
        selected_branch = visible_branches.first()

    return visible_branches, can_switch_branch, selected_branch


def _resolve_date_range(request):
    """يرجع (start_date, end_date, month, year, is_single_month)."""
    today = date.today()
    start_param = _parse_date(request.GET.get('start_date'))
    end_param = _parse_date(request.GET.get('end_date'))

    if start_param and end_param and start_param <= end_param:
        start_date, end_date = start_param, end_param
        month, year = start_date.month, start_date.year
    else:
        month = _parse_int(request.GET.get('month')) or today.month
        year = _parse_int(request.GET.get('year')) or today.year
        if not (1 <= month <= 12):
            month = today.month
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])

    is_single_month = (
        start_date == date(start_date.year, start_date.month, 1)
        and end_date == date(end_date.year, end_date.month, monthrange(end_date.year, end_date.month)[1])
        and start_date.year == end_date.year
        and start_date.month == end_date.month
    )
    return start_date, end_date, month, year, is_single_month


def resolve_filters(request, user):
    visible_branches, can_switch_branch, selected_branch = _resolve_branch(request, user)
    start_date, end_date, month, year, is_single_month = _resolve_date_range(request)

    branch_scope = Branch.objects.filter(id=selected_branch.id) if selected_branch else visible_branches

    # الدورات مشتركة بين كل الفروع، فمش بنفلترها حسب الفرع المختار
    available_courses = Course.objects.filter(is_active=True).order_by('name')
    requested_course_id = _parse_int(request.GET.get('course'))
    selected_course = available_courses.filter(id=requested_course_id).first() if requested_course_id else None

    collector_ids = Income.objects.filter(
        branch__in=branch_scope, date__range=(start_date, end_date)
    ).exclude(collected_by__isnull=True).values_list('collected_by_id', flat=True).distinct()
    available_employees = list(User.objects.filter(id__in=collector_ids).order_by('first_name', 'last_name'))
    requested_employee_id = _parse_int(request.GET.get('employee'))
    selected_employee = next((e for e in available_employees if e.id == requested_employee_id), None)

    payment_status = request.GET.get('payment_status')
    if payment_status not in ('paid', 'unpaid'):
        payment_status = 'all'

    return {
        'visible_branches': visible_branches,
        'can_switch_branch': can_switch_branch,
        'selected_branch': selected_branch,
        'branch_scope': branch_scope,
        'start_date': start_date,
        'end_date': end_date,
        'month': month,
        'year': year,
        'is_single_month': is_single_month,
        'available_courses': available_courses,
        'selected_course': selected_course,
        'available_employees': available_employees,
        'selected_employee': selected_employee,
        'payment_status': payment_status,
    }


# =============================================================================
# 2. حساب البيانات (Data computation)
# =============================================================================

def _base_querysets(filters):
    income_qs = Income.objects.filter(
        branch__in=filters['branch_scope'],
        date__range=(filters['start_date'], filters['end_date']),
    )
    if filters['selected_course']:
        income_qs = income_qs.filter(course_id=filters['selected_course'].id)
    if filters['selected_employee']:
        income_qs = income_qs.filter(collected_by_id=filters['selected_employee'].id)

    # المصروفات تحترم الفرع والتاريخ فقط: لا يوجد مفهوم "دورة" أو "محصل طالب" للمصروف
    expense_qs = Expense.objects.filter(
        branch__in=filters['branch_scope'],
        date__range=(filters['start_date'], filters['end_date']),
    )
    return income_qs, expense_qs


def _has_installment_subquery():
    """طالب دفع أي قسط في نفس الفرع - بغض النظر عن الفترة المختارة حالياً،
    لأن اكتمال الدفع صفة تراكمية للطالب مش مرتبطة بنافذة تاريخ معينة."""
    return Exists(Income.objects.filter(
        party_name=OuterRef('party_name'),
        branch=OuterRef('branch'),
        income_type='installment',
    ))


def _apply_payment_status(income_qs, payment_status):
    if payment_status not in ('paid', 'unpaid'):
        return income_qs
    qualifying_names = income_qs.filter(income_type='registration').annotate(
        has_installment=_has_installment_subquery()
    ).filter(has_installment=(payment_status == 'paid')).values('party_name')
    return income_qs.filter(party_name__in=qualifying_names)


def _distinct_students(qs):
    return qs.exclude(party_name='').values('party_name').distinct().count()


def _compute_cards(qualifying_income_qs, expense_qs):
    totals = qualifying_income_qs.aggregate(
        reg_amount=Sum('amount', filter=Q(income_type='registration')),
        coll_amount=Sum('amount', filter=Q(income_type='installment')),
    )
    reg_amount = float(totals['reg_amount'] or 0)
    coll_amount = float(totals['coll_amount'] or 0)
    expense_total = float(expense_qs.aggregate(total=Sum('amount'))['total'] or 0)

    return {
        'registration_amount': reg_amount,
        'collection_amount': coll_amount,
        'registered_students': _distinct_students(qualifying_income_qs.filter(income_type='registration')),
        'paid_students': _distinct_students(qualifying_income_qs),
        'expense_total': expense_total,
        'net_total': reg_amount + coll_amount - expense_total,
    }


def _month_bounds_list(start_date, end_date):
    buckets = []
    cur = date(start_date.year, start_date.month, 1)
    end_marker = date(end_date.year, end_date.month, 1)
    while cur <= end_marker:
        buckets.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return buckets


def _day_list(start_date, end_date):
    buckets = []
    cur = start_date
    while cur <= end_date:
        buckets.append(cur)
        cur = date.fromordinal(cur.toordinal() + 1)
    return buckets


def _compute_chart(qualifying_income_qs, expense_qs, start_date, end_date):
    daily = (end_date - start_date).days <= CHART_DAILY_THRESHOLD_DAYS
    # date هو DateField بالفعل: TruncDate عليه بيكسر sqlite بخطأ user-defined function،
    # فبنستخدم F('date') مباشرة بدل ما نطبّق trunc غير لازم أصلاً
    trunc = F('date') if daily else TruncMonth('date')
    buckets = _day_list(start_date, end_date) if daily else _month_bounds_list(start_date, end_date)
    label_fmt = '%Y-%m-%d' if daily else '%Y-%m'

    income_rows = qualifying_income_qs.annotate(bucket=trunc).values('bucket').annotate(
        reg=Sum('amount', filter=Q(income_type='registration')),
        coll=Sum('amount', filter=Q(income_type='installment')),
    )
    expense_rows = expense_qs.annotate(bucket=trunc).values('bucket').annotate(total=Sum('amount'))

    reg_by_bucket = {r['bucket']: float(r['reg'] or 0) for r in income_rows}
    coll_by_bucket = {r['bucket']: float(r['coll'] or 0) for r in income_rows}
    expense_by_bucket = {r['bucket']: float(r['total'] or 0) for r in expense_rows}

    return {
        'labels': [b.strftime(label_fmt) for b in buckets],
        'registration': [reg_by_bucket.get(b, 0) for b in buckets],
        'collection': [coll_by_bucket.get(b, 0) for b in buckets],
        'expense': [expense_by_bucket.get(b, 0) for b in buckets],
    }


def _compute_recent_activities(qualifying_income_qs, expense_qs):
    incomes = qualifying_income_qs.select_related('branch').order_by('-created_at')[:RECENT_ACTIVITIES_PER_TYPE]
    expenses = expense_qs.select_related('branch').order_by('-created_at')[:RECENT_ACTIVITIES_PER_TYPE]

    activities = []
    for income in incomes:
        activities.append({
            'type': 'income',
            'icon': 'fa-money-bill-wave',
            'title': 'تحصيل قسط' if income.income_type == 'installment' else 'تسجيل جديد',
            'description': f"{income.party_name or 'غير محدد'} - {income.amount:,.0f} ر.س",
            'branch': income.branch.name,
            'created_at': income.created_at.isoformat(),
        })
    for expense in expenses:
        activities.append({
            'type': 'expense',
            'icon': 'fa-wallet',
            'title': expense.get_category_display(),
            'description': f"{expense.description[:30]} - {expense.amount:,.0f} ر.س",
            'branch': expense.branch.name,
            'created_at': expense.created_at.isoformat(),
        })

    activities.sort(key=lambda a: a['created_at'], reverse=True)
    for a in activities:
        a['time'] = datetime.fromisoformat(a['created_at']).strftime('%Y-%m-%d %H:%M')
    return activities[:RECENT_ACTIVITIES_LIMIT]


def _compute_top_students(qualifying_income_qs):
    def top(income_type):
        rows = qualifying_income_qs.filter(income_type=income_type).exclude(party_name='').values(
            'party_name'
        ).annotate(total=Sum('amount'), count=Count('id')).order_by('-total')[:TOP_N]
        return [{'name': r['party_name'], 'total': float(r['total'] or 0), 'count': r['count']} for r in rows]

    return top('installment'), top('registration')


def _compute_top_courses(qualifying_income_qs):
    most_registered = qualifying_income_qs.filter(
        income_type='registration', course__isnull=False
    ).values('course_id', 'course__name').annotate(
        students_count=Count('party_name', distinct=True)
    ).order_by('-students_count')[:TOP_N]

    highest_revenue = qualifying_income_qs.filter(course__isnull=False).values(
        'course_id', 'course__name'
    ).annotate(total=Sum('amount')).order_by('-total')[:TOP_N]

    return (
        [{'course': r['course__name'], 'students_count': r['students_count']} for r in most_registered],
        [{'course': r['course__name'], 'total': float(r['total'] or 0)} for r in highest_revenue],
    )


def _compute_paid_vs_unpaid(base_income_qs):
    """يُحسب من قبل تطبيق فلتر حالة الدفع نفسه (وإلا صار الاستعلام دائريًا)."""
    qs = base_income_qs.filter(income_type='registration').exclude(party_name='').annotate(
        has_installment=_has_installment_subquery()
    )
    paid = qs.filter(has_installment=True).values('party_name').distinct().count()
    unpaid = qs.filter(has_installment=False).values('party_name').distinct().count()
    return {'paid': paid, 'unpaid': unpaid}


def _compute_top_employees(qualifying_income_qs):
    def top(income_type):
        rows = list(qualifying_income_qs.filter(income_type=income_type).exclude(
            collected_by__isnull=True
        ).values('collected_by').annotate(count=Count('id'), amount=Sum('amount')).order_by('-amount')[:TOP_N])
        users = User.objects.in_bulk([r['collected_by'] for r in rows])
        result = []
        for r in rows:
            user = users.get(r['collected_by'])
            if not user:
                continue
            result.append({
                'name': user.get_full_name() or user.username,
                'count': r['count'],
                'amount': float(r['amount'] or 0),
            })
        return result

    return top('registration'), top('installment')


def _compute_branch_comparison(qualifying_income_qs, filters):
    if filters['selected_branch'] or not filters['can_switch_branch']:
        return None

    rows = qualifying_income_qs.values('branch_id', 'branch__name').annotate(
        reg_amount=Sum('amount', filter=Q(income_type='registration')),
        coll_amount=Sum('amount', filter=Q(income_type='installment')),
        registered_students=Count('party_name', filter=Q(income_type='registration'), distinct=True),
        paid_students=Count('party_name', distinct=True),
    ).order_by('-coll_amount')

    targets = {}
    if filters['is_single_month']:
        for t in BranchTarget.objects.filter(
            branch_id__in=[r['branch_id'] for r in rows], year=filters['year'], month=filters['month']
        ):
            targets[t.branch_id] = float(t.amount)

    result = []
    for r in rows:
        reg = float(r['reg_amount'] or 0)
        coll = float(r['coll_amount'] or 0)
        target = targets.get(r['branch_id'], 0)
        result.append({
            'branch': r['branch__name'],
            'registration_amount': reg,
            'collection_amount': coll,
            'registered_students': r['registered_students'],
            'paid_students': r['paid_students'],
            'target': target,
            'achievement_percentage': round((reg + coll) / target * 100, 1) if target > 0 else None,
        })
    return result


def compute_dashboard_data(user, filters):
    base_income_qs, expense_qs = _base_querysets(filters)
    qualifying_income_qs = _apply_payment_status(base_income_qs, filters['payment_status'])

    top_collected_students, top_registered_students = _compute_top_students(qualifying_income_qs)
    most_registered_courses, highest_revenue_courses = _compute_top_courses(qualifying_income_qs)
    top_employees_by_registrations, top_employees_by_collections = _compute_top_employees(qualifying_income_qs)

    cards = _compute_cards(qualifying_income_qs, expense_qs)

    monthly_target = None
    if filters['is_single_month']:
        target_amount = BranchTarget.objects.filter(
            branch__in=filters['branch_scope'], year=filters['year'], month=filters['month']
        ).aggregate(total=Sum('amount'))['total'] or 0
        target_amount = float(target_amount)
        achieved = cards['registration_amount'] + cards['collection_amount']
        monthly_target = {
            'target': target_amount,
            'achieved': achieved,
            'percentage': round(achieved / target_amount * 100, 1) if target_amount > 0 else 0,
        }

    return {
        'cards': cards,
        'expense_scope_note': bool(
            filters['selected_course'] or filters['selected_employee'] or filters['payment_status'] != 'all'
        ),
        'monthly_target': monthly_target,
        'chart': _compute_chart(qualifying_income_qs, expense_qs, filters['start_date'], filters['end_date']),
        'recent_activities': _compute_recent_activities(qualifying_income_qs, expense_qs),
        'reports': {
            'top_collected_students': top_collected_students,
            'top_registered_students': top_registered_students,
            'most_registered_courses': most_registered_courses,
            'highest_revenue_courses': highest_revenue_courses,
            'students_count': cards['paid_students'],
            'paid_vs_unpaid': _compute_paid_vs_unpaid(base_income_qs),
            'top_employees_by_registrations': top_employees_by_registrations,
            'top_employees_by_collections': top_employees_by_collections,
            'branch_comparison': _compute_branch_comparison(qualifying_income_qs, filters),
        },
    }


# =============================================================================
# 3. تجميع الحمولة الكاملة (Payload orchestration)
# =============================================================================

def get_dashboard_payload(request, user):
    filters = resolve_filters(request, user)
    data = compute_dashboard_data(user, filters)

    data['meta'] = {
        'can_switch_branch': filters['can_switch_branch'],
        'selected_branch': filters['selected_branch'].id if filters['selected_branch'] else None,
        'branches': [{'id': b.id, 'name': b.name} for b in filters['visible_branches']],
        'start_date': filters['start_date'].isoformat(),
        'end_date': filters['end_date'].isoformat(),
        'month': filters['month'],
        'year': filters['year'],
        'is_single_month': filters['is_single_month'],
        'available_courses': [{'id': c.id, 'name': c.name} for c in filters['available_courses']],
        'selected_course': filters['selected_course'].id if filters['selected_course'] else None,
        'available_employees': [
            {'id': e.id, 'name': e.get_full_name() or e.username} for e in filters['available_employees']
        ],
        'selected_employee': filters['selected_employee'].id if filters['selected_employee'] else None,
        'payment_status': filters['payment_status'],
    }
    return data
