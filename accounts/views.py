from datetime import date
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from reports.views import export_to_pdf
from .models import User
from .forms import UserCreateForm, UserUpdateForm  # سأعطيك كود الفورم أيضاً

@login_required
def profile(request):
    """صفحة الملف الشخصي"""
    return render(request, 'accounts/profile.html', {'user': request.user})




# شرط: فقط الأدمن هو من يدير المستخدمين
def admin_only(user):
    return user.is_superuser or user.user_type == 'admin'

# 1. قائمة المستخدمين
@login_required
@user_passes_test(admin_only)
def user_list(request):
    users = User.objects.all()
    form = UserCreateForm() # تأكد أن الاسم مطابق لما في الـ HTML
    return render(request, 'accounts/user_list.html', {'users': users, 'form': form})

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