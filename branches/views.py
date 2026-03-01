from django import forms
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Branch, BranchTarget
from datetime import date

@login_required
def branch_list(request):
    """قائمة الفروع"""
    if request.user.is_superuser or request.user.user_type == 'admin':
        branches = Branch.objects.filter(is_active=True)
    else:
        branches = Branch.objects.filter(id=request.user.branch_id) if request.user.branch else Branch.objects.none()
    
    return render(request, 'branches/branch_list.html', {'branches': branches})


@login_required
def branch_detail(request, pk):
    """تفاصيل الفرع"""
    branch = get_object_or_404(Branch, pk=pk)
    
    # التحقق من الصلاحيات
    if not request.user.is_superuser and request.user.branch != branch:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    
    return render(request, 'branches/branch_detail.html', {'branch': branch})


from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import BranchForm, BranchTargetForm


@login_required
def branch_add(request):
    # السماح فقط للمديرين بإضافة فروع
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء الفرع بنجاح!')
            return redirect('branches:branch_list')
        else:
            messages.error(request, 'يرجى تصحيح الأخطاء أدناه.')
    else:
        form = BranchForm()

    return render(request, 'branches/branch_form.html', {'form': form, 'title': 'إضافة فرع جديد'})


@login_required
def branch_edit(request, pk):
    # جلب بيانات الفرع المطلوب تعديله أو إظهار 404 إذا لم يوجد
    branch = get_object_or_404(Branch, pk=pk)

    # التحقق من الصلاحيات (للمديرين فقط)
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST':
        # تمرير instance=branch ليعرف الـ Form أننا نعدل سجلاً موجوداً
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, f'تم تحديث بيانات {branch.name} بنجاح!')
            return redirect('branches:branch_detail', pk=branch.pk)
        else:
            messages.error(request, 'يرجى مراجعة الأخطاء وتصحيحها.')
    else:
        # ملء الـ Form بالبيانات الحالية للفرع
        form = BranchForm(instance=branch)

    return render(request, 'branches/branch_form.html', {
        'form': form,
        'title': f'تعديل فرع: {branch.name}',
        'is_edit': True
    })


@login_required
def target_add(request):
    branch_id = request.GET.get('branch')  # بنجيب الـ ID من الرابط (الـ GET)
    branch = get_object_or_404(Branch, id=branch_id)

    if request.method == 'POST':
        form = BranchTargetForm(request.POST)
        if form.is_valid():
            target = form.save(commit=False)
            target.branch = branch  # السطر ده هو اللي بيضمن إن الفرع اتسيف صح
            target.save()
            messages.success(request, "تم الحفظ بنجاح")
            return redirect('branches:branch_detail', pk=branch.id)
        else:
            # لو في خطأ في البيانات اطبعها عشان تعرف ليه مش بتسيف
            print(form.errors)
    else:
        form = BranchTargetForm(initial={'branch': branch, 'year': date.today().year})
        form.fields['branch'].widget = forms.HiddenInput()

    return render(request, 'branches/target_form.html', {'form': form, 'branch': branch})

@login_required
def target_edit(request, pk):
    target = get_object_or_404(BranchTarget, pk=pk)
    if request.method == 'POST':
        form = BranchTargetForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الهدف بنجاح")
            return redirect('branches:branch_detail', pk=target.branch.pk)
    else:
        form = BranchTargetForm(instance=target)
    return render(request, 'branches/target_form.html', {'form': form, 'title': 'تعديل الهدف الشهري'})