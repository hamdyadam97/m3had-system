import os
import re
from django import forms
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import date
from branches.models import Branch
from courses.models import Course
from accounts.models import User
from .models import Income, Expense


class IncomeForm(forms.ModelForm):
    """نموذج إضافة/تعديل الإيراد مع تحقق متقدم"""
    
    class Meta:
        model = Income
        fields = ['branch', 'date', 'income_type', 'party_name', 'id_number', 'amount',
                  'payment_method', 'payment_location', 'bank_account_number', 'course', 'collected_by', 'notes']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'max': date.today().isoformat()
            }),
            'income_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'income-type-select'
            }),
            'party_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم الشخص أو الجهة'
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'رقم الهوية أو الملف'
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
            'course': forms.Select(attrs={
                'class': 'form-select',
            }),
            'collected_by': forms.Select(attrs={
                'class': 'form-select',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'أي ملاحظات إضافية...'
            }),
        }
        labels = {
            'branch': 'الفرع',
            'date': 'التاريخ',
            'income_type': 'نوع الإيراد',
            'party_name': 'الاسم / الجهة',
            'id_number': 'رقم الهوية / الملف',
            'amount': 'المبلغ',
            'payment_method': 'طريقة الدفع',
            'payment_location': 'مكان الدفع',
            'bank_account_number': 'رقم الحساب البنكي',
            'course': 'الدورة/الدبلومة',
            'collected_by': 'المحصل',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # تحديد الفروع المتاحة
        if user:
            if user.is_superuser or user.is_admin():
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
            elif user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif user.branch_id:
                self.fields['branch'].queryset = Branch.objects.filter(id=user.branch_id, is_active=True)
                self.fields['branch'].initial = user.branch
                if user.user_type == 'employee':
                    self.fields['branch'].widget = forms.HiddenInput()
            else:
                self.fields['branch'].queryset = Branch.objects.none()
        
        # تحديد الدورات المتاحة
        self.fields['course'].queryset = Course.objects.filter(is_active=True)
        
        # تحديد المحصلين (من طاقم العمل فقط)
        self.fields['collected_by'].queryset = User.objects.filter(
            is_active=True, user_type__in=['employee', 'branch_manager', 'accountant']
        ).order_by('first_name', 'last_name')
        
        # لو المستخدم موظف عادي، نحدده كمحصل افتراضي
        if user and user.user_type == 'employee':
            self.fields['collected_by'].initial = user
    
    def clean_date(self):
        """التحقق من التاريخ"""
        income_date = self.cleaned_data.get('date')
        if income_date:
            today = date.today()
            if income_date > today:
                raise forms.ValidationError('لا يمكن تسجيل إيراد بتاريخ في المستقبل')
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
            bank_account = re.sub(r'\s+', '', bank_account)
            if not re.match(r'^\d{10,20}$', bank_account):
                raise forms.ValidationError('رقم الحساب البنكي غير صالح (يجب أن يكون 10-20 رقم)')
        elif bank_account:
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

    def clean(self):
        """التحقق المتقاطع من البيانات"""
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
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
            if user.is_superuser or user.is_admin():
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
            if expense_date > today:
                raise forms.ValidationError('لا يمكن تسجيل مصروف بتاريخ في المستقبل')
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
            if not re.match(r'^[\w\-]+$', receipt_number):
                raise forms.ValidationError('رقم الإيصال يجب أن يحتوي على حروف وأرقام و(-) فقط')
        return receipt_number

    def clean_receipt_image(self):
        """التحقق من صورة الإيصال"""
        receipt_image = self.cleaned_data.get('receipt_image')
        if receipt_image:
            if receipt_image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('حجم الملف كبير جداً (الحد الأقصى 5 ميجابايت)')
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
            if self.user.is_superuser or self.user.is_admin():
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


class ExcelStyleTransactionForm(forms.Form):
    """نموذج تسجيل حركة مالية بنفس أسلوب ملف الـ Excel (بدون تسجيل طلاب)"""

    TRANSACTION_TYPE_CHOICES = [
        ('registration', 'تسجيل'),
        ('installment', 'دفعه'),

    ]

    PAYMENT_METHOD_CHOICES = [
        ('mada', 'مدى'),
        ('visa', 'فيزا'),
        ('mastercard', 'ماستر'),
        ('bank_transfer', 'تحويل بنكي'),
        ('', '---'),
    ]

    party_name = forms.CharField(
        max_length=200,
        label='الاسم / الجهة',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم الشخص أو الجهة',
        })
    )

    id_number = forms.CharField(
        required=False,
        max_length=50,
        label='الرقم / الهوية',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'رقم الهوية أو الملف'
        })
    )

    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        label='طريقة الدفع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label='المبلغ',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )

    date = forms.DateField(
        label='تاريخ الدفع',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    registration_date = forms.DateField(
        required=False,
        label='تاريخ التسجيل',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    transaction_type = forms.ChoiceField(
        choices=TRANSACTION_TYPE_CHOICES,
        label='نوع العملية',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        label='الفرع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(is_active=True),
        required=False,
        label='الدورة/الدبلومة',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    city = forms.CharField(
        required=False,
        max_length=100,
        label='المدينة',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'المدينة'
        })
    )

    collected_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=True,
        label='المحصل',
        error_messages={'required': 'المحصل مطلوب لجميع أنواع العمليات'},
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    transaction_number = forms.CharField(
        required=False,
        max_length=50,
        label='رقم العملية',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'رقم العملية / الإيصال'
        })
    )

    notes = forms.CharField(
        required=False,
        label='ملاحظات',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'ملاحظات إضافية...'
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # تحديد الفروع المتاحة
        if user:
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif user.is_superuser or user.is_admin():
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
            else:
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch
        
        # تحديد الدورات المتاحة
        self.fields['course'].queryset = Course.objects.filter(is_active=True)
        
        # تحديد المحصلين
        self.fields['collected_by'].queryset = User.objects.filter(
            is_active=True,
            user_type__in=['employee', 'branch_manager', 'accountant']
        ).order_by('first_name', 'last_name')
        
        # تحديد المحصل الافتراضي للموظف العادي
        if user and user.user_type == 'employee':
            self.fields['collected_by'].initial = user

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= 0:
                raise forms.ValidationError('المبلغ يجب أن يكون أكبر من صفر')
            if amount > 1000000:
                raise forms.ValidationError('المبلغ كبير جداً')
        return amount

    def clean_date(self):
        income_date = self.cleaned_data.get('date')
        if income_date:
            from datetime import date as dt_date
            today = dt_date.today()
            if income_date > today:
                raise forms.ValidationError('لا يمكن تسجيل إيراد بتاريخ في المستقبل')
            min_date = today.replace(year=today.year - 1)
            if income_date < min_date:
                raise forms.ValidationError('التاريخ قديم جداً')
        return income_date


class ExcelImportForm(forms.Form):
    """نموذج استيراد ملف Excel"""

    excel_file = forms.FileField(
        label='ملف Excel',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        label='الفرع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif not (user.is_superuser or user.is_admin()):
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch

    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ('.xlsx', '.xls'):
                raise forms.ValidationError('يجب رفع ملف Excel بصيغة .xlsx أو .xls')
        return file

    def clean_branch(self):
        """التحقق من أن المستخدم يمكنه الاستيراد للفرع المختار"""
        branch = self.cleaned_data.get('branch')
        user = self.user
        if not branch:
            raise forms.ValidationError('يجب اختيار الفرع')
        if user:
            if user.is_superuser or user.is_admin():
                return branch
            if user.user_type == 'regional_manager' and branch not in user.managed_branches.all():
                raise forms.ValidationError('لا يمكنك الاستيراد إلى فرع خارج نطاق إدارتك')
            if user.branch and branch.id != user.branch_id:
                raise forms.ValidationError('لا يمكنك الاستيراد إلى فرع آخر')
        return branch


class ExcelMappingForm(forms.Form):
    """نموذج ربط أعمدة Excel بالحقول"""

    step = forms.CharField(widget=forms.HiddenInput(), initial='import')
    temp_file = forms.CharField(widget=forms.HiddenInput())
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True), widget=forms.HiddenInput())

    party_name = forms.IntegerField(required=False, label='الاسم / الجهة', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    id_number = forms.IntegerField(required=False, label='رقم الهوية / الملف', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    payment_method = forms.IntegerField(required=False, label='طريقة الدفع', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    amount = forms.IntegerField(label='المبلغ', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    date = forms.IntegerField(label='تاريخ الدفع', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    transaction_type = forms.IntegerField(required=False, label='نوع العملية', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    city = forms.IntegerField(required=False, label='المدينة', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    collector_name = forms.IntegerField(required=False, label='اسم المحصل', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    transaction_number = forms.IntegerField(required=False, label='رقم العملية', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    course = forms.IntegerField(required=False, label='الدورة / الدبلومة', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    notes = forms.IntegerField(required=False, label='ملاحظات', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))

    def clean_amount(self):
        val = self.cleaned_data.get('amount')
        if val is None:
            raise forms.ValidationError('يجب تحديد عمود المبلغ')
        return val

    def clean_date(self):
        val = self.cleaned_data.get('date')
        if val is None:
            raise forms.ValidationError('يجب تحديد عمود التاريخ')
        return val


class ExcelStyleExpenseForm(forms.Form):
    """نموذج تسجيل مصروف بنفس أسلوب ملف الـ Excel"""

    CATEGORY_CHOICES = [
        ('salaries', 'رواتب'),
        ('rent', 'إيجار'),
        ('utilities', 'مرافق (كهرباء، مياه، إنترنت)'),
        ('supplies', 'مستلزمات'),
        ('marketing', 'تسويق'),
        ('maintenance', 'صيانة'),
        ('bank', 'البنك (مصروفات ورسوم بنكية دورية)'),
        ('other', 'أخرى'),
    ]

    description = forms.CharField(
        max_length=200,
        label='الوصف',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'وصف المصروف',
        })
    )

    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        label='فئة المصروف',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label='المبلغ',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )

    date = forms.DateField(
        label='تاريخ الصرف',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        label='الفرع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    receipt_number = forms.CharField(
        required=False,
        max_length=50,
        label='رقم الإيصال/الفاتورة',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'رقم الإيصال (اختياري)'
        })
    )

    notes = forms.CharField(
        required=False,
        label='ملاحظات',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'ملاحظات إضافية...'
        })
    )

    receipt_image = forms.ImageField(
        required=False,
        label='صورة الإيصال',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user:
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif user.is_superuser or user.is_admin():
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
            else:
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= 0:
                raise forms.ValidationError('المبلغ يجب أن يكون أكبر من صفر')
            if amount > 1000000:
                raise forms.ValidationError('المبلغ كبير جداً')
        return amount

    def clean_date(self):
        expense_date = self.cleaned_data.get('date')
        if expense_date:
            from datetime import date as dt_date
            today = dt_date.today()
            if expense_date > today:
                raise forms.ValidationError('لا يمكن تسجيل مصروف بتاريخ في المستقبل')
            min_date = today.replace(year=today.year - 1)
            if expense_date < min_date:
                raise forms.ValidationError('التاريخ قديم جداً')
        return expense_date


class ExcelExpenseImportForm(forms.Form):
    """نموذج استيراد ملف Excel للمصروفات"""

    excel_file = forms.FileField(
        label='ملف Excel',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        label='الفرع',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif not (user.is_superuser or user.is_admin()):
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch

    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ('.xlsx', '.xls'):
                raise forms.ValidationError('يجب رفع ملف Excel بصيغة .xlsx أو .xls')
        return file

    def clean_branch(self):
        """التحقق من أن المستخدم يمكنه الاستيراد للفرع المختار"""
        branch = self.cleaned_data.get('branch')
        user = self.user
        if not branch:
            raise forms.ValidationError('يجب اختيار الفرع')
        if user:
            if user.is_superuser or user.is_admin():
                return branch
            if user.user_type == 'regional_manager' and branch not in user.managed_branches.all():
                raise forms.ValidationError('لا يمكنك الاستيراد إلى فرع خارج نطاق إدارتك')
            if user.branch and branch.id != user.branch_id:
                raise forms.ValidationError('لا يمكنك الاستيراد إلى فرع آخر')
        return branch


class ExcelExpenseMappingForm(forms.Form):
    """نموذج ربط أعمدة Excel بالحقول (مصروفات)"""

    step = forms.CharField(widget=forms.HiddenInput(), initial='import')
    temp_file = forms.CharField(widget=forms.HiddenInput())
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True), widget=forms.HiddenInput())

    description = forms.IntegerField(required=False, label='الوصف', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    category = forms.IntegerField(required=False, label='فئة المصروف', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    amount = forms.IntegerField(label='المبلغ', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    date = forms.IntegerField(label='تاريخ الصرف', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    receipt_number = forms.IntegerField(required=False, label='رقم الإيصال', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))
    notes = forms.IntegerField(required=False, label='ملاحظات', widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}))

    def clean_amount(self):
        val = self.cleaned_data.get('amount')
        if val is None:
            raise forms.ValidationError('يجب تحديد عمود المبلغ')
        return val

    def clean_date(self):
        val = self.cleaned_data.get('date')
        if val is None:
            raise forms.ValidationError('يجب تحديد عمود التاريخ')
        return val


# ==========================================
# Formsets for Excel-style multi-row entry
# ==========================================

class BaseExcelStyleTransactionFormSet(forms.BaseFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['user'] = self.user
        return super()._construct_form(i, **kwargs)


class BaseExcelStyleExpenseFormSet(forms.BaseFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['user'] = self.user
        return super()._construct_form(i, **kwargs)


ExcelStyleTransactionFormSet = forms.formset_factory(
    ExcelStyleTransactionForm,
    formset=BaseExcelStyleTransactionFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
)

ExcelStyleExpenseFormSet = forms.formset_factory(
    ExcelStyleExpenseForm,
    formset=BaseExcelStyleExpenseFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
)
