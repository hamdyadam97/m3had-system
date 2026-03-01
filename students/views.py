from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from .models import Student
from .forms import StudentForm


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

    # 3. التقسيم لصفحات (20 طالب في الصفحة)
    paginator = Paginator(student_queryset, 20)
    page_number = request.GET.get('page')
    students = paginator.get_page(page_number)

    return render(request, 'students/student_list.html', {'students': students})


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
    """إضافة طالب جديد مع تثبيت الفرع تلقائياً للموظف"""
    if request.method == 'POST':
        form = StudentForm(request.POST, user=request.user)
        if form.is_valid():
            student = form.save(commit=False)

            # إذا لم يكن أدمن، نجبر السيستم على تسجيل الطالب في فرع المستخدم
            if not request.user.is_admin():
                student.branch = request.user.branch

            student.save()
            messages.success(request, f'تم إضافة الطالب {student.name} بنجاح.')
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