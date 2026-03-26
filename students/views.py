from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from .models import Student, InstallmentPlan
from .forms import StudentForm
from branches.models import Branch


@login_required
@permission_required('students.view_student', raise_exception=True)
def student_list(request):
    """قائمة الطلاب مع فلترة حسب صلاحية الوصول (فرع، إقليمي، عام)"""
    user = request.user

    # 1. تحسين الاستعلام بجلب البيانات المرتبطة (الفرع والدورة) في استعلام واحد
    student_queryset = Student.objects.select_related('branch', 'course').filter(is_active=True).order_by('-id')

    # 2. تحديد نطاق الرؤية (Scope)
    if user.is_superuser or user.user_type == 'admin':
        pass  # يرى الكل
    elif user.user_type == 'regional_manager':
        student_queryset = student_queryset.filter(branch__in=user.managed_branches.all())
    else:
        if user.branch:
            student_queryset = student_queryset.filter(branch=user.branch)
        else:
            student_queryset = student_queryset.none()

    # 3. الفلترة حسب الطلب
    payment_status = request.GET.get('payment_status')
    branch_filter = request.GET.get('branch')
    payment_method = request.GET.get('payment_method')

    if branch_filter:
        student_queryset = student_queryset.filter(branch_id=branch_filter)

    if payment_method:
        student_queryset = student_queryset.filter(payment_method=payment_method)

    if payment_status == 'overdue':
        # الطلاب المتأخرين
        student_queryset = [s for s in student_queryset if s.has_overdue_installments()]
    elif payment_status == 'paid':
        student_queryset = [s for s in student_queryset if s.is_fully_paid()]
    elif payment_status == 'pending':
        student_queryset = [s for s in student_queryset if not s.is_fully_paid() and s.get_total_paid() > 0]

    # 4. الإحصائيات
    all_students = Student.objects.select_related('branch', 'course').filter(is_active=True)
    if not (user.is_superuser or user.user_type == 'admin'):
        if user.user_type == 'regional_manager':
            all_students = all_students.filter(branch__in=user.managed_branches.all())
        elif user.branch:
            all_students = all_students.filter(branch=user.branch)

    overdue_count = sum(1 for s in all_students if s.has_overdue_installments())
    paid_count = sum(1 for s in all_students if s.is_fully_paid())
    pending_count = len(all_students) - overdue_count - paid_count

    # 5. التقسيم لصفحات (20 طالب في الصفحة)
    if isinstance(student_queryset, list):
        # إذا تم تحويلها لقائمة (بسبب الفلترة)
        paginator = Paginator(student_queryset, 20)
        page_number = request.GET.get('page')
        students = paginator.get_page(page_number)
    else:
        paginator = Paginator(student_queryset, 20)
        page_number = request.GET.get('page')
        students = paginator.get_page(page_number)

    # الفروع للفلتر
    if user.is_superuser or user.user_type == 'admin':
        branches = Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        branches = user.managed_branches.all()
    else:
        branches = Branch.objects.filter(id=user.branch.id) if user.branch else Branch.objects.none()

    return render(request, 'students/student_list.html', {
        'students': students,
        'branches': branches,
        'overdue_count': overdue_count,
        'paid_count': paid_count,
        'pending_count': pending_count,
    })


@login_required
@permission_required('students.view_student', raise_exception=True)
def student_detail(request, pk):
    """عرض تفاصيل الطالب مع حماية أمنية للفرع"""
    user = request.user
    student = get_object_or_404(Student, pk=pk)

    # حماية: التحقق من أن الطالب يتبع نطاق صلاحيات المستخدم
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch

    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied

    return render(request, 'students/student_detail.html', {'student': student})


@login_required
@permission_required('students.add_student', raise_exception=True)
def student_add(request):
    if request.method == 'POST':
        form = StudentForm(request.POST, user=request.user)
        if form.is_valid():
            student = form.save(commit=False)
            user = request.user

            # 1. إذا كان المستخدم أدمن أو سوبر يوزر، ناخذ الفرع من الفورم
            if user.is_superuser or user.user_type == 'admin':
                branch = form.cleaned_data.get('branch')
                if branch:
                    student.branch = branch
                else:
                    messages.error(request, "يجب اختيار فرع للطالب.")
                    return render(request, 'students/student_form.html', {'form': form, 'title': 'إضافة طالب جديد'})
            
            # 2. إذا كان مدير إقليمي
            elif user.user_type == 'regional_manager':
                branch = form.cleaned_data.get('branch')
                # نتحقق أن الفرع المختار ضمن فروعه المدارة
                if branch and branch in user.managed_branches.all():
                    student.branch = branch
                else:
                    messages.error(request, "يجب اختيار فرع صالح من فروعك المدارة.")
                    return render(request, 'students/student_form.html', {'form': form, 'title': 'إضافة طالب جديد'})
            
            # 3. إذا كان موظف فرع أو مدير فرع، نثبت فرعه هو
            else:
                if user.branch:
                    student.branch = user.branch
                else:
                    messages.error(request, "لم يتم تعيين فرع لك. يرجى التواصل مع الإدارة.")
                    return render(request, 'students/student_form.html', {'form': form, 'title': 'إضافة طالب جديد'})

            # الآن student.branch مؤكد أنه ليس None
            student.save()

            # إنشاء خطة التقسيط
            # إنشاء خطة التقسيط
            if student.payment_method == 'installment' and student.installment_count > 1:
                from .installment_models import InstallmentPlan

                # حذف أي خطة قديمة لنفس الطالب للأمان
                InstallmentPlan.objects.filter(student=student).delete()

                # التعديل هنا: استخدمنا total_amount بدل total_price
                plan = InstallmentPlan.objects.create(
                    student=student,
                    total_amount=student.total_price,  # تأكد إن حقل الطالب اسمه total_price
                    number_of_installments=student.installment_count,
                    installment_amount=student.installment_amount,
                    first_installment_date=student.first_installment_date or student.registration_date
                )
                # توليد الأقساط الفردية في جدول Installment
                plan.create_installments()
            messages.success(request, f'تم إضافة الطالب {student.full_name} بنجاح.')
            return redirect('students:student_detail', pk=student.pk)
    else:
        form = StudentForm(user=request.user)

    return render(request, 'students/student_form.html', {'form': form, 'title': 'إضافة طالب جديد'})

@login_required
@permission_required('students.change_student', raise_exception=True)
def student_edit(request, pk):
    """تعديل بيانات الطالب مع حماية النطاق"""
    user = request.user
    student = get_object_or_404(Student, pk=pk)

    # منع التعديل إذا كان الطالب خارج نطاق صلاحيات المستخدم
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch

    if not (is_admin or is_regional or is_branch_user):
        messages.error(request, "لا تملك صلاحية تعديل بيانات هذا الطالب.")
        return redirect('students:student_list')

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات الطالب بنجاح.')
            return redirect('students:student_detail', pk=student.pk)
    else:
        form = StudentForm(instance=student, user=request.user)

    return render(request, 'students/student_form.html', {'form': form, 'title': 'تعديل بيانات الطالب'})


# ============== إعدادات الإشعارات ==============

from .notification_models import NotificationSettings
from .forms import NotificationSettingsForm


@login_required
def notification_settings(request):
    """صفحة إعدادات الإشعارات"""
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        raise PermissionDenied
    
    settings_obj = NotificationSettings.get_settings()
    
    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ الإعدادات بنجاح.')
            return redirect('students:notification_settings')
    else:
        form = NotificationSettingsForm(instance=settings_obj)
    
    return render(request, 'students/notification_settings.html', {
        'form': form,
        'title': 'إعدادات الإشعارات'
    })


@login_required
def notification_logs(request):
    """سجل الإشعارات المرسلة"""
    from .notification_models import NotificationLog
    
    if not (request.user.is_superuser or request.user.user_type == 'admin'):
        raise PermissionDenied
    
    logs = NotificationLog.objects.select_related('student', 'installment').order_by('-created_at')[:100]
    
    return render(request, 'students/notification_logs.html', {
        'logs': logs,
        'title': 'سجل الإشعارات'
    })


@login_required
def installment_plan_detail(request, student_pk):
    """عرض خطة الأقساط للطالب"""
    student = get_object_or_404(Student, pk=student_pk)

    # حماية: التحقق من أن الطالب يتبع نطاق صلاحيات المستخدم
    user = request.user
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch

    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied

    # ✅ نستخدم try/except عشان نتعامل مع DoesNotExist
    plan = None
    installments = []

    try:
        plan = student.installment_plan  # ✅ ده هيرفع DoesNotExist لو مفيش
        installments = plan.installments.all().order_by('installment_number')
    except (ObjectDoesNotExist, InstallmentPlan.DoesNotExist, AttributeError):
        # ✅ الطالب ماعندوش خطة تقسيط
        plan = None
        installments = []

    return render(request, 'students/installment_plan.html', {
        'student': student,
        'plan': plan,
        'installments': installments,
    })

import pandas as pd
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML


def get_filtered_queryset(request):
    """دالة مساعدة للحصول على الطلاب المفلترين بناءً على صلاحيات المستخدم والفلاتر المختارة"""
    user = request.user
    # نفس منطق الفلترة اللي في الـ View الأساسي بتاعك
    queryset = Student.objects.select_related('branch', 'course').filter(is_active=True)

    # فلترة الصلاحيات
    if not (user.is_superuser or user.user_type == 'admin'):
        if user.user_type == 'regional_manager':
            queryset = queryset.filter(branch__in=user.managed_branches.all())
        else:
            queryset = queryset.filter(branch=user.branch)

    # فلترة الاختيارات (Branch, Payment Status, etc.)
    branch_id = request.GET.get('branch')
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)

    # يمكنك إضافة بقية الفلاتر هنا...
    return queryset


@login_required
def export_excel(request):
    students = get_filtered_queryset(request)

    # تجهيز البيانات
    data = []
    for s in students:
        data.append({
            'الاسم': s.full_name,
            'الهاتف': s.phone,
            'الدورة': s.course.name,
            'طريقة الدفع': s.get_payment_method_display(),
            'الإجمالي': s.total_price,
            'المدفوع': s.get_total_paid(),
            'المتبقي': s.get_remaining_amount(),
            'تاريخ التسجيل': s.registration_date.strftime('%Y-%m-%d')
        })

    df = pd.DataFrame(data)

    # تصدير إلى ملف Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="students_list.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='الطلاب')

    return response


from datetime import date


@login_required
def export_pdf(request):
    students = get_filtered_queryset(request)  # دالة الفلترة التي شرحناها سابقاً

    # حساب الإجماليات للتقرير
    total_collected = sum(s.get_total_paid() for s in students)
    total_remaining = sum(s.get_remaining_amount() for s in students)

    html_string = render_to_string('students/pdf_template.html', {
        'students': students,
        'today': date.today(),
        'total_collected': total_collected,
        'total_remaining': total_remaining,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="students_report.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response


from django.http import JsonResponse
from courses.models import Course

def get_courses_by_branch(request):
    branch_id = request.GET.get('branch_id')
    # تأكد من وجود .values('id', 'name', 'price') ليرسل السعر للمتصفح
    courses = Course.objects.filter(branches__id=branch_id, is_active=True).values('id', 'name', 'price')
    return JsonResponse(list(courses), safe=False)