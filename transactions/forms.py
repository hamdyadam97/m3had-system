from django.db import models
from branches.models import Branch
from .models import Income, Expense
from courses.models import Course
from django import forms
from students.models import Student
from django import forms
from django.db import models
from .models import Income, Student, Course
from django import forms
from django.db import models
from django.db.models import Q, Sum, Case, When, Value, IntegerField
from .models import Income, Student, Course


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['date', 'income_type', 'student', 'course', 'amount',
                  'payment_method', 'payment_location', 'bank_account_number', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'income_type': forms.Select(attrs={'class': 'form-select', 'id': 'income-type-select'}),
            'student': forms.Select(attrs={'class': 'form-select', 'id': 'student-select'}),
            'course': forms.Select(attrs={'class': 'form-select', 'id': 'course-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'id': 'amount-input', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_location': forms.Select(attrs={'class': 'form-select'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # نبدأ بقائمة فارغة
        self.fields['student'].queryset = Student.objects.none()
        self.fields['course'].queryset = Course.objects.none()

        # ✅ لو فيه POST data مع student
        if self.data.get('student'):
            try:
                student_id = int(self.data.get('student'))
                student = Student.objects.get(pk=student_id)
                self.fields['student'].queryset = Student.objects.filter(pk=student_id)

                if student.course:
                    self.fields['course'].queryset = Course.objects.filter(pk=student.course.id)
                    self.initial['course'] = student.course.id
            except (ValueError, Student.DoesNotExist):
                pass

        # ✅ لو فيه income_type
        if self.data.get('income_type'):
            income_type = self.data.get('income_type')
            self._filter_students_by_type(income_type)

        elif self.instance.pk:
            self.fields['student'].queryset = Student.objects.filter(pk=self.instance.student_id)
            self.fields['course'].queryset = Course.objects.filter(pk=self.instance.course_id)

    def _filter_students_by_type(self, income_type):
        """فلترة الطلاب حسب نوع الإيراد"""
        if not self.user:
            return

        selected_student_id = self.data.get('student')

        # ✅ تحديد الفروع المتاحة
        if self.user.is_superuser or self.user.user_type == 'admin':
            base_query = Student.objects.filter(is_active=True)
        elif self.user.user_type == 'regional_manager':
            base_query = Student.objects.filter(
                branch__in=self.user.managed_branches.all(),
                is_active=True
            )
        elif self.user.branch:
            base_query = Student.objects.filter(branch=self.user.branch, is_active=True)
        else:
            base_query = Student.objects.none()

        if income_type == 'registration':
            # ✅ طلاب جدد = اللي معندهمش إيرادات خالص (total_paid = 0)
            # نستخدم annotate عشان نحسب المدفوع
            from django.db.models import OuterRef, Subquery
            from transactions.models import Income as IncomeModel

            # نجيب الطلاب اللي معندهمش إيرادات
            students_with_income = IncomeModel.objects.values('student').distinct()
            filtered = base_query.exclude(id__in=students_with_income)

        else:  # installment
            # ✅ طلاب قدامة = اللي عندهم رصيد مستحق
            # نستخدم طريقة أبسط: الطلاب اللي دفعوا قبل كده ولسه عليهم
            from transactions.models import Income as IncomeModel

            # الطلاب اللي لهم إيرادات
            students_with_income = IncomeModel.objects.values('student').distinct()
            # ولسه السعر الكلي أكبر من المدفوع (نحسبه roughly)
            filtered = base_query.filter(id__in=students_with_income)

        # ✅ نضيف الطالب المختار لو مش في القائمة
        if selected_student_id:
            try:
                selected = Student.objects.filter(pk=int(selected_student_id))
                self.fields['student'].queryset = (filtered | selected).distinct()
            except ValueError:
                self.fields['student'].queryset = filtered
        else:
            self.fields['student'].queryset = filtered



class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['branch', 'category', 'amount', 'date', 'notes', 'receipt_image']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_image': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # لو المستخدم مدير فرع، نخفي اختيار الفرع لأنه سيتسجل تلقائياً
        if user and user.branch:
            self.fields['branch'].widget = forms.HiddenInput()
            self.fields['branch'].required = False
        else:
            # لو سوبر يوزر، نظهر اختيار الفروع كلها
            self.fields['branch'].queryset = Branch.objects.all()
            self.fields['branch'].widget.attrs.update({'class': 'form-select'})