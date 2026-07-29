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
    if user.is_superuser or user.is_admin():
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

    form = CourseForm()
    return render(request, 'courses/course_list.html', {'courses': courses, 'form': form})


@login_required
@permission_required('courses.view_course', raise_exception=True)
def course_detail(request, pk):
    """تفاصيل الدورة مع إحصائيات دقيقة حسب صلاحية الرؤية"""
    user = request.user
    course = get_object_or_404(Course, pk=pk)

    from transactions.models import Income

    # تحديد نطاق البيانات (هل يرى إحصائيات الفرع أم الكل؟)
    if user.is_superuser or user.is_admin():
        income_queryset = Income.objects.filter(course=course)
    elif user.user_type == 'regional_manager':
        branches = user.managed_branches.all()
        income_queryset = Income.objects.filter(course=course, branch__in=branches)
    else:
        income_queryset = Income.objects.filter(course=course, branch=user.branch)

    # حساب الإحصائيات
    total_income = income_queryset.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'course': course,
        'students_count': '',
        'total_income': total_income,
    }

    return render(request, 'courses/course_detail.html', context)


@login_required
@permission_required('courses.add_course', raise_exception=True)
def course_create(request):
    """إضافة دورة جديدة"""
    course = None  # 🔴 مهم: نعرف course = None في الأول

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)  # 🔴 commit=False الأول

            # لو عندك created_by في الموديل
            # course.created_by = request.user

            course.save()  # 🔴 نحفظ الأول عشان نقدر نضيف M2M
            form.save_m2m()  # 🔴 نحفظ العلاقات Many-to-Many (branches)

            # إذا كان موظف فرع، نربط الدورة بفرعه تلقائياً
            if not request.user.is_admin() and request.user.branch:
                course.branches.add(request.user.branch)

            messages.success(request, 'تم إنشاء الدورة بنجاح.')
            return redirect('courses:course_list')
        else:
            # 🔴 نطبع الأخطاء في الـ Console
            print("❌ Form errors:", form.errors)
            print("❌ Non-field errors:", form.non_field_errors())
            messages.error(request, 'يوجد أخطاء في البيانات المدخلة.')
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {
        'form': form,
        'course': course,  # 🔴 هنا course = None لو GET، أو = course لو POST success (بس هنا بيرجع redirect)
        'title': 'إضافة دورة جديدة'
    })


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


import pandas as pd
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import date


# --- دالة مساعدة للحصول على الدورات المفلترة حسب الصلاحية ---
def get_filtered_courses(request):
    user = request.user
    queryset = Course.objects.filter(is_active=True).order_by('-id')

    if not (user.is_superuser or user.is_admin()):
        if user.user_type == 'regional_manager':
            queryset = queryset.filter(branches__in=user.managed_branches.all()).distinct()
        elif user.branch:
            queryset = queryset.filter(branches=user.branch)
        else:
            queryset = queryset.none()
    return queryset


# --- تصدير الدورات إلى Excel ---
@login_required
def course_export_excel(request):
    courses = get_filtered_courses(request)
    data = []
    for c in courses:
        data.append({
            'كود الدورة': c.code,
            'اسم الدورة': c.name,
            'النوع': c.get_course_type_display(),
            'السعر': c.price,
            'المدة (أيام)': c.duration_days,
            'الوصف': c.description,
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="courses_list.xlsx"'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='الدورات')
    return response


# --- تصدير الدورات إلى PDF ملون واحترافي ---
@login_required
def course_export_pdf(request):
    courses = get_filtered_courses(request)
    html_string = render_to_string('courses/course_pdf_template.html', {
        'courses': courses,
        'today': date.today(),
    })
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="courses_report.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response


# --- استيراد دورات من Excel ---
@login_required
@permission_required('courses.add_course', raise_exception=True)
def course_import_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        file = request.FILES['excel_file']
        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f'خطأ في قراءة الملف: {e}')
            return redirect('courses:course_list')

        type_map = {'دبلوم': 'diploma', 'دبلومة': 'diploma', 'دورة': 'course'}
        imported = 0
        errors = []

        for idx, row in df.iterrows():
            excel_row = idx + 2  # +2: صف الـ header + الفهرسة تبدأ من 0
            try:
                code = str(row.get('كود الدورة', '')).strip()
                name = str(row.get('اسم الدورة', '')).strip()
                if not code or code.lower() == 'nan':
                    errors.append(f'صف {excel_row}: كود الدورة مطلوب')
                    continue
                if not name or name.lower() == 'nan':
                    errors.append(f'صف {excel_row}: اسم الدورة مطلوب')
                    continue
                if Course.objects.filter(code=code).exists():
                    errors.append(f'صف {excel_row}: الكود "{code}" مستخدم بالفعل')
                    continue

                type_raw = str(row.get('النوع', '')).strip()
                course_type = type_map.get(type_raw, 'course')

                price = row.get('السعر', 0)
                price = float(price) if pd.notna(price) else 0

                duration = row.get('المدة (أيام)', row.get('المدة', 30))
                duration = int(duration) if pd.notna(duration) else 30

                description = row.get('الوصف', '')
                description = str(description).strip() if pd.notna(description) else ''

                course = Course.objects.create(
                    code=code,
                    name=name,
                    course_type=course_type,
                    price=price,
                    duration_days=duration,
                    description=description,
                )
                # إذا كان المستخدم يتبع فرعاً معيناً نربط الدورة به تلقائياً
                if not request.user.is_superuser and request.user.branch:
                    course.branches.add(request.user.branch)
                imported += 1
            except Exception as e:
                errors.append(f'صف {excel_row}: {e}')

        if imported:
            messages.success(request, f'تم استيراد {imported} دورة بنجاح!')
        for err in errors[:10]:
            messages.warning(request, err)
        if len(errors) > 10:
            messages.warning(request, f'و{len(errors) - 10} خطأ إضافي لم يتم عرضهم.')

    return redirect('courses:course_list')


# --- تحميل نموذج Excel لاستيراد الدورات ---
@login_required
def download_course_template(request):
    columns = ['كود الدورة', 'اسم الدورة', 'النوع', 'السعر', 'المدة (أيام)', 'الوصف']
    rows = [
        ['CRS-101', 'دورة السلامة المهنية', 'دورة', 500, 30, 'دورة تدريبية عامة'],
        ['DIP-201', 'دبلوم إدارة الموارد البشرية', 'دبلوم', 3000, 90, 'برنامج دبلوم متكامل'],
    ]
    df = pd.DataFrame(rows, columns=columns)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="courses_import_template.xlsx"'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='الدورات')
    return response


