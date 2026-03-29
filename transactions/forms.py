import re
from django import forms
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import date
from branches.models import Branch
from .models import Income, Expense
from courses.models import Course
from students.models import Student


class IncomeForm(forms.ModelForm):
    """نموذج إضافة/تعديل الإيراد مع تحقق متقدم"""
    
    class Meta:
        model = Income
        fields = ['date', 'income_type', 'student', 'course', 'amount',
                  'payment_method', 'payment_location', 'bank_account_number', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'max': date.today().isoformat()
            }),
            'income_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'income-type-select'
            }),
            'student': forms.Select(attrs={
                'class': 'form-select',
                'id': 'student-select'
            }),
            'course': forms.Select(attrs={
                'class': 'form-select',
                'id': 'course-select'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'amount-input',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_location': forms.Select(attrs={'class': 'form-select'}),
            'bank_account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'رقم الحساب (للتحويل البنكي فقط)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'أي ملاحظات إضافية...'
            }),
        }
        labels = {
            'date': 'التاريخ',
            'income_type': 'نوع الإيراد',
            'student': 'الطالب',
            'course': 'الدورة / الدبلومة',
            'amount': 'المبلغ',
            'payment_method': 'طريقة الدفع',
            'payment_location': 'مكان الدفع',
            'bank_account_number': 'رقم الحساب البنكي',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # تحديد الفروع المتاحة للمستخدم
        self.available_branches = self._get_available_branches()
        
        # نبدأ بقائمة فارغة
        self.fields['student'].queryset = Student.objects.none()
        self.fields['course'].queryset = Course.objects.none()

        # ✅ لو فيه POST data مع student
        if self.data.get('student'):
            try:
                student_id = int(self.data.get('student'))
                student = Student.objects.get(pk=student_id)
                # التحقق من أن الطالب في فرع مسموح للمستخدم
                if student.branch in self.available_branches:
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
            # تعديل سجل موجود
            if self.instance.student and self.instance.student.branch in self.available_branches:
                self.fields['student'].queryset = Student.objects.filter(pk=self.instance.student_id)
                self.fields['course'].queryset = Course.objects.filter(pk=self.instance.course_id)

    def _get_available_branches(self):
        """تحديد الفروع المتاحة للمستخدم الحالي"""
        if not self.user:
            return Branch.objects.none()
        
        if self.user.is_superuser or self.user.user_type == 'admin':
            # الأدمن يرى كل الفروع
            return Branch.objects.filter(is_active=True)
        elif self.user.user_type == 'regional_manager':
            # المدير الإقليمي يرى فروعه المدارة
            return self.user.managed_branches.filter(is_active=True)
        elif self.user.branch_id:
            # الموظف/مدير الفرع يرى فرعه فقط
            return Branch.objects.filter(id=self.user.branch_id, is_active=True)
        else:
            return Branch.objects.none()

    def _get_base_student_query(self):
        """الاستعلام الأساسي للطلاب حسب صلاحيات المستخدم"""
        return Student.objects.filter(
            branch__in=self.available_branches,
            is_active=True
        )

    def _filter_students_by_type(self, income_type):
        """فلترة الطلاب حسب نوع الإيراد"""
        if not self.user:
            return

        selected_student_id = self.data.get('student')
        
        # ✅ الاستعلام الأساسي - طلاب الفروع المتاحة فقط
        base_query = self._get_base_student_query()

        if income_type == 'registration':
            # ✅ طلاب جدد = اللي معندهمش إيرادات خالص
            from transactions.models import Income as IncomeModel
            students_with_income = IncomeModel.objects.values('student').distinct()
            filtered = base_query.exclude(id__in=students_with_income)

        else:  # installment
            # ✅ طلاب قدامة = اللي عندهم رصيد مستحق
            from transactions.models import Income as IncomeModel
            students_with_income = IncomeModel.objects.values('student').distinct()
            filtered = base_query.filter(id__in=students_with_income)

        # ✅ نضيف الطالب المختار لو مش في القائمة (للتعديل)
        if selected_student_id:
            try:
                selected = Student.objects.filter(pk=int(selected_student_id))
                # التحقق من أن الطالب المختار في فرع مسموح
                if selected.first() and selected.first().branch in self.available_branches:
                    self.fields['student'].queryset = (filtered | selected).distinct()
                else:
                    self.fields['student'].queryset = filtered
            except ValueError:
                self.fields['student'].queryset = filtered
        else:
            self.fields['student'].queryset = filtered

    def clean_date(self):
        """التحقق من التاريخ"""
        income_date = self.cleaned_data.get('date')
        if income_date:
            today = date.today()
            # التاريخ لا يمكن أن يكون في المستقبل
            if income_date > today:
                raise forms.ValidationError('لا يمكن تسجيل إيراد بتاريخ في المستقبل')
            # التاريخ لا يمكن أن يتجاوز سنة في الماضي
            min_date = today.replace(year=today.year - 1)
            if income_date < min_date:
                raise forms.ValidationError('التاريخ قديم جداً، يجب أن يكون خلال السنة الماضية')
        return income_date

    def clean_amount(self):
        """التحقق من المبلغ"""
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= 0:
                raise forms.ValidationError('المبلغ يجب أن يكون أكبر من صفر')
            if amount > 1000000:
                raise forms.ValidationError('المبلغ كبير جداً، يرجى التحقق')
            # التحقق من عدد الكسور العشرية
            amount_str = str(amount)
            if '.' in amount_str:
                decimals = len(amount_str.split('.')[1])
                if decimals > 2:
                    raise forms.ValidationError('المبلغ يجب أن يكون بحد أقصى منزلتين عشريتين')
        return amount

    def clean_bank_account_number(self):
        """التحقق من رقم الحساب البنكي"""
        bank_account = self.cleaned_data.get('bank_account_number')
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method == 'bank_transfer':
            if not bank_account:
                raise forms.ValidationError('يجب إدخال رقم الحساب البنكي عند اختيار التحويل البنكي')
            # إزالة المسافات
            bank_account = re.sub(r'\s+', '', bank_account)
            # التحقق من أن الرقم يحتوي على أرقام فقط (10-20 رقم)
            if not re.match(r'^\d{10,20}$', bank_account):
                raise forms.ValidationError('رقم الحساب البنكي غير صالح (يجب أن يكون 10-20 رقم)')
        elif bank_account:
            # إذا كانت طريقة الدفع ليست تحويل بنكي، نحذف رقم الحساب
            return None
        
        return bank_account

    def clean_notes(self):
        """تنظيف الملاحظات"""
        notes = self.cleaned_data.get('notes')
        if notes:
            notes = notes.strip()
            if len(notes) > 1000:
                raise forms.ValidationError('الملاحظات طويلة جداً (الحد الأقصى 1000 حرف)')
        return notes

    def clean_student(self):
        """التحقق من أن الطالب في فرع مسموح للمستخدم"""
        student = self.cleaned_data.get('student')
        if student:
            if student.branch not in self.available_branches:
                raise forms.ValidationError('لا يمكنك تسجيل إيراد لطالب من فرع آخر!')
        return student

    def clean(self):
        """التحقق المتقاطع من البيانات"""
        cleaned_data = super().clean()
        
        student = cleaned_data.get('student')
        course = cleaned_data.get('course')
        amount = cleaned_data.get('amount')
        income_type = cleaned_data.get('income_type')
        
        # التحقق من وجود الطالب والدورة
        if not student:
            self.add_error('student', 'يجب اختيار الطالب')
        else:
            # التحقق مرة أخرى من الفرع
            if student.branch not in self.available_branches:
                self.add_error('student', 'لا يمكنك تسجيل إيراد لطالب من فرع آخر!')
        
        if not course:
            self.add_error('course', 'يجب اختيار الدورة')
        
        # التحقق من تطابق الدورة مع الطالب
        if student and course:
            if student.course_id and student.course_id != course.id:
                self.add_error('course', 'الدورة المختارة لا تتطابق مع دورة الطالب المسجلة')
        
        # التحقق من المبلغ المتبقي للطالب
        if student and amount and income_type == 'installment':
            remaining = student.get_remaining_amount()
            if amount > remaining:
                self.add_error('amount', f'المبلغ أكبر من الرصيد المتبقي ({remaining:.2f})')
        
        # التحقق من وجود مبلغ
        if amount and amount <= 0:
            self.add_error('amount', 'المبلغ يجب أن يكون أكبر من صفر')
        
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    """نموذج إضافة/تعديل المصروف مع تحقق متقدم"""
    
    # إضافة حقل الوصف بشكل صريح
    description = forms.CharField(
        max_length=200,
        label='الوصف',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'وصف المصروف (مثال: إيجار شهر يناير)'
        })
    )
    
    class Meta:
        model = Expense
        fields = ['branch', 'category', 'description', 'amount', 'date', 'receipt_number', 'receipt_image', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'max': date.today().isoformat()
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'رقم الفاتورة أو الإيصال (اختياري)'
            }),
            'receipt_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'أي ملاحظات إضافية...'
            }),
        }
        labels = {
            'branch': 'الفرع',
            'category': 'فئة المصروف',
            'description': 'الوصف',
            'amount': 'المبلغ',
            'date': 'التاريخ',
            'receipt_number': 'رقم الإيصال/الفاتورة',
            'receipt_image': 'صورة الإيصال',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.user = user

        # تحديد الفروع المتاحة
        if user:
            if user.is_superuser or user.user_type == 'admin':
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
            elif user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif user.branch_id:
                # الموظف/مدير الفرع
                self.fields['branch'].queryset = Branch.objects.filter(id=user.branch_id, is_active=True)
                self.fields['branch'].initial = user.branch
                # إخفاء حقل الفرع للموظف العادي
                if user.user_type == 'employee':
                    self.fields['branch'].widget = forms.HiddenInput()
            else:
                self.fields['branch'].queryset = Branch.objects.none()

    def clean_date(self):
        """التحقق من التاريخ"""
        expense_date = self.cleaned_data.get('date')
        if expense_date:
            today = date.today()
            # التاريخ لا يمكن أن يكون في المستقبل
            if expense_date > today:
                raise forms.ValidationError('لا يمكن تسجيل مصروف بتاريخ في المستقبل')
            # التاريخ لا يمكن أن يتجاوز سنة في الماضي
            min_date = today.replace(year=today.year - 1)
            if expense_date < min_date:
                raise forms.ValidationError('التاريخ قديم جداً، يجب أن يكون خلال السنة الماضية')
        return expense_date

    def clean_amount(self):
        """التحقق من المبلغ"""
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= 0:
                raise forms.ValidationError('المبلغ يجب أن يكون أكبر من صفر')
            if amount > 1000000:
                raise forms.ValidationError('المبلغ كبير جداً، يرجى التحقق')
            # التحقق من عدد الكسور العشرية
            amount_str = str(amount)
            if '.' in amount_str:
                decimals = len(amount_str.split('.')[1])
                if decimals > 2:
                    raise forms.ValidationError('المبلغ يجب أن يكون بحد أقصى منزلتين عشريتين')
        return amount

    def clean_description(self):
        """التحقق من الوصف"""
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
            if len(description) < 3:
                raise forms.ValidationError('الوصف قصير جداً (3 أحرف على الأقل)')
            if len(description) > 200:
                raise forms.ValidationError('الوصف طويل جداً (الحد الأقصى 200 حرف)')
            # التحقق من عدم وجود أحرف خاصة خطرة
            if re.search(r'[<>{}/\\\\|]', description):
                raise forms.ValidationError('الوصف يحتوي على أحرف غير مسموح بها')
        return description

    def clean_receipt_number(self):
        """التحقق من رقم الإيصال"""
        receipt_number = self.cleaned_data.get('receipt_number')
        if receipt_number:
            receipt_number = receipt_number.strip()
            if len(receipt_number) > 50:
                raise forms.ValidationError('رقم الإيصال طويل جداً')
            # التحقق من أن الرقم يحتوي على أحرف وأرقام فقط
            if not re.match(r'^[\w\-]+$', receipt_number):
                raise forms.ValidationError('رقم الإيصال يجب أن يحتوي على حروف وأرقام و(-) فقط')
        return receipt_number

    def clean_receipt_image(self):
        """التحقق من صورة الإيصال"""
        receipt_image = self.cleaned_data.get('receipt_image')
        if receipt_image:
            # التحقق من حجم الملف (5 ميجا كحد أقصى)
            if receipt_image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('حجم الملف كبير جداً (الحد الأقصى 5 ميجابايت)')
            
            # التحقق من نوع الملف
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
            if receipt_image.content_type not in allowed_types:
                raise forms.ValidationError('نوع الملف غير مسموح به (مسموح: JPG, PNG, GIF, PDF)')
        return receipt_image

    def clean_notes(self):
        """تنظيف الملاحظات"""
        notes = self.cleaned_data.get('notes')
        if notes:
            notes = notes.strip()
            if len(notes) > 1000:
                raise forms.ValidationError('الملاحظات طويلة جداً (الحد الأقصى 1000 حرف)')
        return notes

    def clean_branch(self):
        """التحقق من الفرع"""
        branch = self.cleaned_data.get('branch')
        if not branch and self.user and self.user.branch_id:
            branch = self.user.branch
        
        if branch and self.user:
            # التحقق من صلاحيات المستخدم للفرع
            if self.user.is_superuser or self.user.user_type == 'admin':
                return branch
            elif self.user.user_type == 'regional_manager':
                if branch not in self.user.managed_branches.all():
                    raise forms.ValidationError('لا يمكنك تسجيل مصروف في هذا الفرع!')
            elif self.user.branch_id and branch.id != self.user.branch_id:
                raise forms.ValidationError('لا يمكنك تسجيل مصروف في فرع آخر!')
        
        return branch

    def clean(self):
        """التحقق المتقاطع"""
        cleaned_data = super().clean()
        
        category = cleaned_data.get('category')
        description = cleaned_data.get('description')
        
        return cleaned_data
