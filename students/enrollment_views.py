from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Student
from .enrollment_models import Enrollment
from .enrollment_forms import EnrollmentForm, EnrollmentStatusForm
from .installment_models import InstallmentPlan


@login_required
@permission_required('students.view_student', raise_exception=True)
def enrollment_list(request, student_pk):
    """عرض جميع تسجيلات الطالب في الدورات"""
    student = get_object_or_404(Student, pk=student_pk)
    
    # التحقق من الصلاحيات
    user = request.user
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch
    
    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied
    
    enrollments = student.enrollments.all().select_related('course', 'branch')
    
    # هل يمكن إضافة تسجيل جديد؟
    can_add_enrollment = student.can_enroll_in_new_course()
    
    context = {
        'student': student,
        'enrollments': enrollments,
        'can_add_enrollment': can_add_enrollment,
        'active_enrollment': student.get_active_enrollment(),
    }
    return render(request, 'students/enrollment_list.html', context)


@login_required
@permission_required('students.add_student', raise_exception=True)
def enrollment_add(request, student_pk):
    """إضافة تسجيل جديد للطالب في دورة"""
    student = get_object_or_404(Student, pk=student_pk)
    
    # التحقق من الصلاحيات
    user = request.user
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch
    
    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied

    # داخل enrollment_add في views.py
    if not student.can_enroll_in_new_course():
        # لو المنع بسبب "عدم الدفع"
        if student.get_total_paid() <= 0:
            messages.error(
                request,
                f'عذراً! الطالب لديه حجز سابق لدورة ({student.course.name}) لم يتم سداده. '
                'يجب دفع القسط الأول أولاً لتتمكن من تسجيله في دورات أخرى.'
            )
        # لو المنع بسبب "دورة نشطة"
        else:
            active_enrollment = student.get_active_enrollment()
            messages.error(
                request,
                f'لا يمكن إضافة تسجيل جديد. الطالب مسجل حالياً في: {active_enrollment.course.name}.'
            )
        return redirect('students:enrollment_list', student_pk=student.pk)
    
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, student=student, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                enrollment = form.save()
                
                # إنشاء خطة تقسيط لو لازم
                if enrollment.payment_method == 'installment' and enrollment.installment_count > 1:
                    plan = InstallmentPlan.objects.create(
                        student=student,
                        total_amount=enrollment.total_price,
                        number_of_installments=enrollment.installment_count,
                        installment_amount=enrollment.installment_amount,
                        first_installment_date=enrollment.first_installment_date or enrollment.enrollment_date
                    )
                    plan.create_installments()
                
                messages.success(
                    request, 
                    f'تم تسجيل الطالب في دورة {enrollment.course.name} بنجاح!'
                )
                return redirect('students:enrollment_list', student_pk=student.pk)
    else:
        # تعيين السعر الافتراضي من آخر دورة مسجل فيها الطالب
        last_enrollment = student.enrollments.first()
        initial_data = {}
        if last_enrollment:
            initial_data['total_price'] = last_enrollment.total_price
            initial_data['payment_method'] = last_enrollment.payment_method
        
        form = EnrollmentForm(student=student, user=request.user, initial=initial_data)
    
    context = {
        'form': form,
        'student': student,
        'title': f'تسجيل {student.full_name} في دورة جديدة',
    }
    return render(request, 'students/enrollment_form.html', context)


@login_required
@permission_required('students.change_student', raise_exception=True)
def enrollment_change_status(request, enrollment_pk):
    """تغيير حالة التسجيل (إكمال/انسحاب/تعليق)"""
    enrollment = get_object_or_404(Enrollment, pk=enrollment_pk)
    student = enrollment.student
    
    # التحقق من الصلاحيات
    user = request.user
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch
    
    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied
    
    if request.method == 'POST':
        form = EnrollmentStatusForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            reason = form.cleaned_data['reason']
            
            with transaction.atomic():
                if action == 'complete':
                    if enrollment.mark_completed():
                        messages.success(
                            request, 
                            f'تم إكمال دورة {enrollment.course.name} بنجاح! يمكن الآن تسجيل الطالب في دورة جديدة.'
                        )
                    else:
                        messages.error(request, 'لا يمكن إكمال الدورة. تأكد من أنها نشطة.')
                
                elif action == 'withdraw':
                    if enrollment.mark_withdrawn(reason):
                        messages.success(
                            request, 
                            f'تم الانسحاب من دورة {enrollment.course.name} بنجاح! يمكن الآن تسجيل الطالب في دورة جديدة.'
                        )
                    else:
                        messages.error(request, 'لا يمكن الانسحاب من الدورة. تأكد من أنها نشطة.')
                
                elif action == 'suspend':
                    enrollment.status = 'suspended'
                    enrollment.save()
                    messages.warning(request, f'تم تعليق الدورة {enrollment.course.name} مؤقتاً.')
            
            return redirect('students:enrollment_list', student_pk=student.pk)
    else:
        form = EnrollmentStatusForm()
    
    context = {
        'form': form,
        'enrollment': enrollment,
        'student': student,
        'title': f'تغيير حالة التسجيل - {enrollment.course.name}',
    }
    return render(request, 'students/enrollment_status_form.html', context)


@login_required
@permission_required('students.view_student', raise_exception=True)
def enrollment_detail(request, enrollment_pk):
    """عرض تفاصيل التسجيل"""
    enrollment = get_object_or_404(Enrollment, pk=enrollment_pk)
    student = enrollment.student
    
    # التحقق من الصلاحيات
    user = request.user
    is_admin = user.user_type == 'admin' or user.is_superuser
    is_regional = user.user_type == 'regional_manager' and student.branch in user.managed_branches.all()
    is_branch_user = user.branch == student.branch
    
    if not (is_admin or is_regional or is_branch_user):
        raise PermissionDenied
    
    # جلب مدفوعات هذا التسجيل
    from transactions.models import Income
    payments = Income.objects.filter(
        student=student,
        course=enrollment.course,
        created_at__date__gte=enrollment.enrollment_date
    ).order_by('-date')
    
    context = {
        'enrollment': enrollment,
        'student': student,
        'payments': payments,
        'total_paid': enrollment.get_total_paid(),
        'remaining': enrollment.get_remaining_amount(),
    }
    return render(request, 'students/enrollment_detail.html', context)
