from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from .forms import CourseForm
from .models import Course


@login_required
@permission_required('courses.view_course', raise_exception=True)
def course_list(request):
    """قائمة الدورات مع فلترة حسب الصلاحيات والفرع"""
    user = request.user

    # البداية بكل الدورات النشطة
    course_queryset = Course.objects.filter(is_active=True).order_by('-id')

    # 1. فلترة الفروع بناءً على نوع المستخدم (Scope)
    if user.is_superuser or user.user_type == 'admin':
        # الأدمن يرى كل الدورات في كل الفروع
        pass
    elif user.user_type == 'regional_manager':
        # المدير الإقليمي يرى الدورات المتاحة في فروعه فقط
        course_queryset = course_queryset.filter(branches__in=user.managed_branches.all()).distinct()
    else:
        # الموظف/مدير الفرع يرى دورات فرعه فقط
        if user.branch:
            course_queryset = course_queryset.filter(branches=user.branch)
        else:
            course_queryset = course_queryset.none()

    # 2. تقسيم الصفحات (Pagination)
    paginator = Paginator(course_queryset, 10)  # 10 دورات في الصفحة
    page_number = request.GET.get('page')
    courses = paginator.get_page(page_number)

    return render(request, 'courses/course_list.html', {'courses': courses})


@login_required
@permission_required('courses.view_course', raise_exception=True)
def course_detail(request, pk):
    """تفاصيل الدورة مع إحصائيات دقيقة حسب صلاحية الرؤية"""
    user = request.user
    course = get_object_or_404(Course, pk=pk)

    from students.models import Student
    from transactions.models import Income

    # تحديد نطاق البيانات (هل يرى إحصائيات الفرع أم الكل؟)
    if user.is_superuser or user.user_type == 'admin':
        students_queryset = Student.objects.filter(course=course)
        income_queryset = Income.objects.filter(course=course)
    elif user.user_type == 'regional_manager':
        branches = user.managed_branches.all()
        students_queryset = Student.objects.filter(course=course, branch__in=branches)
        income_queryset = Income.objects.filter(course=course, branch__in=branches)
    else:
        students_queryset = Student.objects.filter(course=course, branch=user.branch)
        income_queryset = Income.objects.filter(course=course, branch=user.branch)

    # حساب الإحصائيات
    students_count = students_queryset.count()
    total_income = income_queryset.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'course': course,
        'students_count': students_count,
        'total_income': total_income,
    }

    return render(request, 'courses/course_detail.html', context)


@login_required
@permission_required('courses.add_course', raise_exception=True)
def course_create(request):
    """إضافة دورة جديدة"""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            # إذا كان موظف فرع، نربط الدورة بفرعه تلقائياً لو الموديل يدعم ذلك
            if not request.user.is_admin() and request.user.branch:
                course.branches.add(request.user.branch)

            messages.success(request, 'تم إنشاء الدورة بنجاح.')
            return redirect('courses:course_list')
    else:
        form = CourseForm()
    return render(request, 'courses/course_form.html', {'form': form, 'title': 'إضافة دورة جديدة'})


@login_required
@permission_required('courses.change_course', raise_exception=True)
def course_edit(request, pk):
    """تعديل دورة"""
    course = get_object_or_404(Course, pk=pk)

    # حماية: منع موظف فرع من تعديل دورة ليست في فرعه
    if not request.user.is_admin() and request.user.branch not in course.branches.all():
        messages.error(request, "ليس لديك صلاحية لتعديل هذه الدورة.")
        return redirect('courses:course_list')

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث بيانات الدورة.')
            return redirect('courses:course_detail', pk=course.pk)
    else:
        form = CourseForm(instance=course)
    return render(request, 'courses/course_form.html', {'form': form, 'title': 'تعديل الدورة', 'course': course})


@login_required
@permission_required('courses.delete_course', raise_exception=True)
def course_delete_soft(request, pk):
    """أرشفة الدورة (حذف ناعم)"""
    course = get_object_or_404(Course, pk=pk)

    if request.method == 'POST':
        course.is_active = False
        course.save()
        messages.warning(request, f'تم أرشفة الدورة "{course.name}" بنجاح.')
        return redirect('courses:course_list')
    return render(request, 'courses/course_confirm_delete.html', {'course': course})