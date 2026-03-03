from django import forms
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from reports.views import export_to_pdf
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


import pandas as pd
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from .models import Branch


# --- دالة تصدير الفروع إلى Excel ---
@login_required
def export_branches_excel(request):
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    # جلب البيانات
    branches = Branch.objects.all().values('code', 'name', 'phone', 'email', 'address', 'is_active', 'created_at')
    df = pd.DataFrame(list(branches))

    # --- الحل هنا: تحويل العمود لتاريخ بدون منطقة زمنية ---
    if not df.empty and 'created_at' in df.columns:
        # تحويل العمود ليكون Timezone Unaware
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_localize(None)

    # إعادة تسمية الأعمدة للعربية
    df.rename(columns={
        'code': 'كود الفرع',
        'name': 'اسم الفرع',
        'phone': 'رقم الهاتف',
        'email': 'البريد الإلكتروني',
        'address': 'العنوان',
        'is_active': 'نشط',
        'created_at': 'تاريخ الإنشاء'
    }, inplace=True)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=branches_list.xlsx'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Branches')

    return response

# --- دالة استيراد الفروع من Excel ---
@login_required
def import_branches_excel(request):
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']

        try:
            df = pd.read_excel(excel_file)
            success_count = 0
            error_count = 0

            for _, row in df.iterrows():
                try:
                    # التحقق من وجود الفرع بالكود لمنع التكرار أو تحديثه
                    Branch.objects.update_or_create(
                        code=str(row['كود الفرع']),
                        defaults={
                            'name': row['اسم الفرع'],
                            'phone': str(row.get('رقم الهاتف', '')),
                            'email': row.get('البريد الإلكتروني', ''),
                            'address': row.get('العنوان', ''),
                            'is_active': True
                        }
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1

            messages.success(request, f'تم استيراد {success_count} فرع بنجاح! (أخطاء: {error_count})')
        except Exception as e:
            messages.error(request, f'حدث خطأ أثناء قراءة الملف: {str(e)}')

    return redirect('branches:branch_list')


@login_required
def export_branches_pdf(request):
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    branches = Branch.objects.filter(is_active=True)

    context = {
        'branches_list': branches,
        'title': 'تقرير قائمة الفروع المعتمدة',
        'date': date.today(),
        'user': request.user,
        'type': 'branches_report'  # لتمييز الجدول في القالب
    }
    # استدعاء دالة التصدير التي برمجناها سابقاً
    return export_to_pdf(request, context, 'reports/pdf_template.html', "branches_report")