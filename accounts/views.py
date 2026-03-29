from datetime import date
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from reports.views import export_to_pdf
from .models import User
from .forms import UserCreateForm, UserUpdateForm  # سأعطيك كود الفورم أيضاً

@login_required
def profile(request):
    """صفحة الملف الشخصي مع تقرير نشاط الموظف"""
    from transactions.models import Income
    from students.models import Student
    from django.db.models import Sum, Count, Q
    from datetime import date, timedelta
    import json
    
    user = request.user
    today = date.today()
    month_start = today.replace(day=1)
    
    # ====== بيانات نشاط الموظف ======
    
    # 1. إحصائيات التحصيل
    income_stats = Income.objects.filter(collected_by=user).aggregate(
        total_collected=Sum('amount'),
        total_transactions=Count('id'),
        registration_count=Count('id', filter=Q(income_type='registration')),
        installment_count=Count('id', filter=Q(income_type='installment')),
    )
    
    # 2. إحصائيات اليوم
    today_stats = Income.objects.filter(
        collected_by=user,
        date=today
    ).aggregate(
        today_amount=Sum('amount'),
        today_count=Count('id')
    )
    
    # 3. إحصائيات الشهر
    month_stats = Income.objects.filter(
        collected_by=user,
        date__gte=month_start
    ).aggregate(
        month_amount=Sum('amount'),
        month_count=Count('id')
    )
    
    # 4. الطلاب المسجلين على يد هذا الموظف
    registered_students = Student.objects.filter(
        id__in=Income.objects.filter(
            collected_by=user,
            income_type='registration'
        ).values('student_id')
    ).count()
    
    # 5. آخر 30 يوم - بيانات الرسم البياني
    last_30_days = []
    daily_labels = []
    daily_data = []
    
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        day_income = Income.objects.filter(
            collected_by=user,
            date=day
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        daily_labels.append(day.strftime('%d/%m'))
        daily_data.append(float(day_income))
        
        last_30_days.append({
            'date': day,
            'amount': day_income
        })
    
    # 6. أداء الموظف حسب نوع الدفع
    payment_method_stats = Income.objects.filter(
        collected_by=user
    ).values('payment_method').annotate(
        count=Count('id'),
        total=Sum('amount')
    )
    
    payment_labels = []
    payment_data = []
    payment_colors = ['#3498db', '#27ae60', '#f39c12', '#e74c3c']
    
    method_names = {
        'mada': 'مدى',
        'visa': 'فيزا',
        'bank_transfer': 'تحويل بنكي',
        'cash': 'كاش'
    }
    
    for i, stat in enumerate(payment_method_stats):
        method = stat['payment_method']
        payment_labels.append(method_names.get(method, method))
        payment_data.append(float(stat['total']))
    
    # 7. آخر التحصيلات
    recent_transactions = Income.objects.filter(
        collected_by=user
    ).select_related('student', 'course', 'branch').order_by('-created_at')[:10]
    
    # 8. ترتيب الموظف بين زملائه في الفرع
    branch_ranking = []
    if user.branch:
        branch_ranking = list(User.objects.filter(
            branch=user.branch,
            user_type='employee'
        ).annotate(
            total=Sum('income__amount', filter=Q(income__date__gte=month_start))
        ).order_by('-total'))
        
        user_rank = next((i+1 for i, u in enumerate(branch_ranking) if u.id == user.id), '-')
    else:
        user_rank = '-'
    
    context = {
        'user': user,
        # إحصائيات عامة
        'total_collected': income_stats['total_collected'] or 0,
        'total_transactions': income_stats['total_transactions'] or 0,
        'registration_count': income_stats['registration_count'] or 0,
        'installment_count': income_stats['installment_count'] or 0,
        'registered_students': registered_students,
        
        # إحصائيات اليوم والشهر
        'today_amount': today_stats['today_amount'] or 0,
        'today_count': today_stats['today_count'] or 0,
        'month_amount': month_stats['month_amount'] or 0,
        'month_count': month_stats['month_count'] or 0,
        
        # بيانات الرسوم البيانية
        'daily_labels': json.dumps(daily_labels),
        'daily_data': json.dumps(daily_data),
        'payment_labels': json.dumps(payment_labels),
        'payment_data': json.dumps(payment_data),
        'payment_colors': json.dumps(payment_colors[:len(payment_labels)]),
        
        # آخر التحصيلات
        'recent_transactions': recent_transactions,
        
        # الترتيب
        'user_rank': user_rank,
        'branch_employees_count': len(branch_ranking),
    }
    
    return render(request, 'accounts/profile.html', context)




# شرط: فقط الأدمن هو من يدير المستخدمين
def admin_only(user):
    return user.is_superuser or user.user_type == 'admin'

# 1. قائمة المستخدمين
@login_required
@user_passes_test(admin_only)
def user_list(request):
    from django.db.models import Q
    from branches.models import Branch
    
    # بدء الاستعلام الأساسي
    users = User.objects.all().select_related('branch').prefetch_related('groups')
    
    # ====== البحث المتقدم ======
    search_name = request.GET.get('name', '')
    search_type = request.GET.get('user_type', '')
    search_branch = request.GET.get('branch', '')
    search_status = request.GET.get('status', '')
    search_group = request.GET.get('group', '')
    
    # البحث بالاسم (الاسم الأول أو الاسم الأخير أو اسم المستخدم أو الإيميل)
    if search_name:
        users = users.filter(
            Q(first_name__icontains=search_name) |
            Q(last_name__icontains=search_name) |
            Q(username__icontains=search_name) |
            Q(email__icontains=search_name)
        )
    
    # البحث بالنوع
    if search_type:
        users = users.filter(user_type=search_type)
    
    # البحث بالفرع
    if search_branch:
        if search_branch == 'none':
            users = users.filter(branch__isnull=True)
        else:
            users = users.filter(branch_id=search_branch)
    
    # البحث بالحالة
    if search_status:
        is_active = search_status == 'active'
        users = users.filter(is_active=is_active)
    
    # البحث بالمجموعة (الصلاحيات)
    if search_group:
        users = users.filter(groups__id=search_group)
    
    # ====== بيانات للفلاتر ======
    branches = Branch.objects.filter(is_active=True)
    groups = Group.objects.all()
    
    # أنواع المستخدمين
    user_types = User.USER_TYPE_CHOICES
    
    form = UserCreateForm()
    
    context = {
        'users': users,
        'form': form,
        'branches': branches,
        'groups': groups,
        'user_types': user_types,
        # إعادة قيم البحث للقالب
        'search_name': search_name,
        'search_type': search_type,
        'search_branch': search_branch,
        'search_status': search_status,
        'search_group': search_group,
    }
    
    return render(request, 'accounts/user_list.html', context)

# 2. إضافة مستخدم جديد
@login_required
@user_passes_test(admin_only)
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user =form.save()
            group_name = ""
            if user.user_type == 'employee':
                group_name = "Emp"
            elif user.user_type == 'admin':
                group_name = "admin"
            elif user.user_type == 'branch_manager':
                group_name = "manager"
            elif user.user_type == 'accountant':
                group_name = "accountant"
            elif user.user_type == 'regional_manager':
                group_name = "regional_manager"
            if group_name:
                group, created = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)  # إضافة المستخدم للمجموعة فوراً

            messages.success(request, 'تم إنشاء المستخدم وربطه بصلاحياته تلقائياً.')
            return redirect('accounts:user_list')

    else:
        form = UserCreateForm()
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'إضافة مستخدم جديد'})


@login_required
@user_passes_test(admin_only)
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=user_obj)  # هنا صح
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المستخدم.')
            return redirect('accounts:user_list')
    else:
        # التعديل هنا: استخدم UserUpdateForm بدلاً من UserCreateForm
        form = UserUpdateForm(instance=user_obj)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'تعديل مستخدم',
        'user_obj': user_obj
    })

# 4. تفعيل / تعطيل مستخدم (Soft Toggle)
@login_required
@user_passes_test(admin_only)
def user_toggle_status(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj == request.user:
        messages.error(request, 'لا يمكنك تعطيل حسابك الشخصي!')
    else:
        user_obj.is_active = not user_obj.is_active
        user_obj.save()
        status = "تفعيل" if user_obj.is_active else "تعطيل"
        messages.warning(request, f'تم {status} حساب {user_obj.username} بنجاح.')
    return redirect('accounts:user_list')

# 5. عرض البروفايل الشخصي (للمستخدم نفسه)
@login_required
def user_profile(request):
    return render(request, 'accounts/user_profile.html', {'user': request.user})



# --- تصدير الموظفين إلى Excel ---
@login_required
def export_users_excel(request):
    # جلب البيانات الأساسية للموظفين
    users = User.objects.all().values(
        'username', 'first_name', 'last_name', 'email', 'user_type', 'branch__name', 'phone', 'is_active'
    )
    df = pd.DataFrame(list(users))

    # تحسين المسميات للعربية
    df.rename(columns={
        'username': 'اسم المستخدم',
        'first_name': 'الاسم الأول',
        'last_name': 'اسم العائلة',
        'email': 'البريد الإلكتروني',
        'user_type': 'نوع الحساب',
        'branch__name': 'الفرع',
        'phone': 'الهاتف',
        'is_active': 'الحالة'
    }, inplace=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=staff_list.xlsx'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return response


# --- تصدير الموظفين إلى PDF ---
@login_required
def export_users_pdf(request):
    users = User.objects.all().select_related('branch')
    context = {
        'staff_list': users,
        'title': 'تقرير طاقم العمل والمديرين',
        'date': date.today(),
        'user': request.user,
        'type': 'staff_report'  # لتمييزه في القالب الشامل
    }
    # نستخدم نفس الدالة الموحدة اللي عملناها قبل كدا
    return export_to_pdf(request, context, 'reports/pdf_template.html', "staff_report")


@login_required
def import_users_excel(request):
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            success_count = 0

            for _, row in df.iterrows():
                username = str(row['اسم المستخدم']).strip()
                # التأكد أن المستخدم غير موجود مسبقاً
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username,
                        email=row.get('البريد الإلكتروني', ''),
                        password='Password123',  # كلمة سر افتراضية
                        first_name=row.get('الاسم الأول', ''),
                        last_name=row.get('اسم العائلة', ''),
                        phone=str(row.get('الهاتف', '')),
                        user_type=row.get('نوع الحساب', 'employee')  # القيمة الافتراضية
                    )
                    # ربط بالفرع إذا كان موجوداً
                    branch_name = row.get('الفرع')
                    if branch_name:
                        from branches.models import Branch
                        branch = Branch.objects.filter(name=branch_name).first()
                        if branch:
                            user.branch = branch
                            user.save()

                    success_count += 1

            messages.success(request, f'تم استيراد {success_count} موظف بنجاح! كلمة السر الافتراضية: Password123')
        except Exception as e:
            messages.error(request, f'خطأ في الملف: {str(e)}')

    return redirect('accounts:user_list')


# =============================================================================
# إشعارات النظام الداخلية
# =============================================================================

@login_required
def get_notifications(request):
    """
    API لجلب الإشعارات (JSON) - للتحديث الفوري
    """
    from .models import Notification
    
    notifications = request.user.notifications.filter(
        is_read=False
    ).select_related('related_income', 'related_student')[:20]
    
    data = []
    for notif in notifications:
        notif_data = {
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M'),
            'time_ago': _get_time_ago(notif.created_at),
            'icon': _get_notification_icon(notif.notification_type),
            'color': _get_notification_color(notif.notification_type),
        }
        
        # إضافة رابط التفاصيل إن وجد
        if notif.related_income:
            notif_data['link'] = f'/transactions/income/{notif.related_income.id}/'
        elif notif.related_expense:
            notif_data['link'] = f'/transactions/expense/{notif.related_expense.id}/'
        elif notif.related_student:
            notif_data['link'] = f'/students/{notif.related_student.id}/'
        else:
            notif_data['link'] = '#'
        
        data.append(notif_data)
    
    return JsonResponse({
        'notifications': data,
        'unread_count': len(data)
    })


@login_required
def mark_notification_read(request, pk):
    """
    تحديد إشعار كمقروء
    """
    from .models import Notification
    
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    
    return JsonResponse({'success': True})


@login_required
def mark_all_notifications_read(request):
    """
    تحديد كل الإشعارات كمقروءة
    """
    from .models import Notification
    from django.utils import timezone
    
    request.user.notifications.filter(is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    return JsonResponse({'success': True})


@login_required
def notifications_list(request):
    """
    صفحة عرض كل الإشعارات
    """
    from .models import Notification
    
    notifications = request.user.notifications.select_related(
        'related_income', 'related_expense', 'related_student'
    )[:50]
    
    # تقسيم الإشعارات
    unread = [n for n in notifications if not n.is_read]
    read = [n for n in notifications if n.is_read]
    
    return render(request, 'accounts/notifications_list.html', {
        'unread_notifications': unread,
        'read_notifications': read,
    })


# =============================================================================
# دوال مساعدة
# =============================================================================

def _get_time_ago(created_at):
    """تحويل التاريخ إلى نص مثل 'منذ 5 دقائق'"""
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    diff = now - created_at
    
    if diff < timedelta(minutes=1):
        return 'الآن'
    elif diff < timedelta(hours=1):
        minutes = int(diff.seconds / 60)
        return f'منذ {minutes} دقيقة'
    elif diff < timedelta(days=1):
        hours = int(diff.seconds / 3600)
        return f'منذ {hours} ساعة'
    else:
        days = diff.days
        return f'منذ {days} يوم'


def _get_notification_icon(notification_type):
    """إيقونة الإشعار حسب النوع"""
    icons = {
        'income': 'fa-money-bill-wave',
        'expense': 'fa-file-invoice-dollar',
        'installment': 'fa-calendar-check',
        'registration': 'fa-user-plus',
        'system': 'fa-bell',
    }
    return icons.get(notification_type, 'fa-bell')


def _get_notification_color(notification_type):
    """لون الإشعار حسب النوع"""
    colors = {
        'income': 'success',
        'expense': 'danger',
        'installment': 'info',
        'registration': 'primary',
        'system': 'warning',
    }
    return colors.get(notification_type, 'secondary')
