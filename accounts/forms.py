import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from .models import User


class UserCreateForm(UserCreationForm):
    """فورم إنشاء مستخدم جديد مع تشفير كلمة المرور تلقائياً وتحقق متقدم"""
    
    # Custom password validation
    password1 = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='يجب أن تحتوي على 8 أحرف على الأقل، وحرف كبير، ورقم',
    )
    password2 = forms.CharField(
        label='تأكيد كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'user_type', 'branch', 'managed_branches', 'phone')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم المستخدم'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الأول'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم العائلة'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@domain.com'}),
            'user_type': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '01xxxxxxxxx'}),
        }
        labels = {
            'username': 'اسم المستخدم',
            'first_name': 'الاسم الأول',
            'last_name': 'اسم العائلة',
            'email': 'البريد الإلكتروني',
            'user_type': 'نوع المستخدم',
            'branch': 'الفرع',
            'managed_branches': 'الفروع المدارة (للمدير الإقليمي)',
            'phone': 'رقم الهاتف',
        }
        help_texts = {
            'username': 'يجب أن يكون فريداً، حروف وأرقام و(_) فقط',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        
        # تحديث الـ widget attributes
        for field_name, field in self.fields.items():
            if field_name not in ['password1', 'password2']:
                if isinstance(field.widget, forms.CheckboxSelectMultiple):
                    field.widget.attrs.update({'class': 'form-check-input'})
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise forms.ValidationError('اسم المستخدم يجب أن يحتوي على حروف إنجليزية وأرقام و (_) فقط')
        if len(username) < 3:
            raise forms.ValidationError('اسم المستخدم يجب أن يكون 3 أحرف على الأقل')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('هذا البريد الإلكتروني مستخدم بالفعل')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # إزالة المسافات والرموز
            phone = re.sub(r'\s+|-', '', phone)
            # التحقق من صحة الرقم المصري
            if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', phone):
                raise forms.ValidationError('رقم الهاتف غير صالح. يجب أن يبدأ بـ 01 ويكون 11 رقم')
        return phone

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name:
            if len(first_name) < 2:
                raise forms.ValidationError('الاسم الأول قصير جداً')
            if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', first_name):
                raise forms.ValidationError('الاسم يجب أن يحتوي على حروف فقط')
        return first_name.strip()

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if last_name:
            if len(last_name) < 2:
                raise forms.ValidationError('اسم العائلة قصير جداً')
            if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', last_name):
                raise forms.ValidationError('الاسم يجب أن يحتوي على حروف فقط')
        return last_name.strip()

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            if len(password) < 8:
                raise forms.ValidationError('كلمة المرور يجب أن تكون 8 أحرف على الأقل')
            if not re.search(r'[A-Z]', password):
                raise forms.ValidationError('كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل')
            if not re.search(r'[a-z]', password):
                raise forms.ValidationError('كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل')
            if not re.search(r'\d', password):
                raise forms.ValidationError('كلمة المرور يجب أن تحتوي على رقم واحد على الأقل')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise forms.ValidationError('كلمة المرور يجب أن تحتوي على رمز خاص واحد على الأقل (!@#$%^&*)')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'كلمتا المرور غير متطابقتين')
        
        # التحقق من تطابق نوع المستخدم مع الفرع
        user_type = cleaned_data.get('user_type')
        branch = cleaned_data.get('branch')
        
        if user_type in ['branch_manager', 'employee'] and not branch:
            self.add_error('branch', 'يجب اختيار فرع لهذا النوع من المستخدمين')
        
        if user_type == 'regional_manager':
            managed_branches = cleaned_data.get('managed_branches')
            if not managed_branches or managed_branches.count() == 0:
                self.add_error('managed_branches', 'يجب اختيار الفروع المدارة للمدير الإقليمي')
        
        return cleaned_data


class UserUpdateForm(forms.ModelForm):
    """فورم تعديل بيانات المستخدم (بدون كلمة المرور)"""
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'user_type', 'branch', 'phone', 'is_active', 'managed_branches')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الأول'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم العائلة'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@domain.com'}),
            'user_type': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '01xxxxxxxxx'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'managed_branches': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
        }
        labels = {
            'first_name': 'الاسم الأول',
            'last_name': 'اسم العائلة',
            'email': 'البريد الإلكتروني',
            'user_type': 'نوع المستخدم',
            'branch': 'الفرع',
            'phone': 'رقم الهاتف',
            'is_active': 'نشط',
            'managed_branches': 'الفروع المدارة',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            # استبعاد المستخدم الحالي من الفحص
            existing = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا البريد الإلكتروني مستخدم بالفعل')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone = re.sub(r'\s+|-', '', phone)
            if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', phone):
                raise forms.ValidationError('رقم الهاتف غير صالح. يجب أن يبدأ بـ 01 ويكون 11 رقم')
        return phone

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name:
            if len(first_name) < 2:
                raise forms.ValidationError('الاسم الأول قصير جداً')
            if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', first_name):
                raise forms.ValidationError('الاسم يجب أن يحتوي على حروف فقط')
        return first_name.strip()

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if last_name:
            if len(last_name) < 2:
                raise forms.ValidationError('اسم العائلة قصير جداً')
            if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', last_name):
                raise forms.ValidationError('الاسم يجب أن يحتوي على حروف فقط')
        return last_name.strip()

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        branch = cleaned_data.get('branch')
        
        if user_type in ['branch_manager', 'employee'] and not branch:
            self.add_error('branch', 'يجب اختيار فرع لهذا النوع من المستخدمين')
        
        return cleaned_data
