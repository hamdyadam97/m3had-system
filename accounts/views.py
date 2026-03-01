from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import User
from .forms import UserCreateForm # سأعطيك كود الفورم أيضاً

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
    users = User.objects.select_related('branch').all().order_by('-created_at')
    return render(request, 'accounts/user_list.html', {'users': users})

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

# 3. تعديل بيانات مستخدم
@login_required
@user_passes_test(admin_only)
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserCreateForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات المستخدم.')
            return redirect('accounts:user_list')
    else:
        form = UserCreateForm(instance=user_obj)
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'تعديل مستخدم', 'user_obj': user_obj})

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