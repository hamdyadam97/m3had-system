import re
from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import date, timedelta
from .models import Student
from .notification_models import NotificationSettings


class StudentForm(forms.ModelForm):
    """نموذج إضافة/تعديل الطالب مع خيارات التقسيط وتحقق متقدم"""
    
    # خيارات عدد الأقساط
    INSTALLMENT_CHOICES = [
        (1, 'دفعة واحدة (كامل المبلغ)'),
        (2, 'قسطين'),
        (3, '3 أقساط'),
        (4, '4 أقساط'),
        (6, '6 أقساط'),
        (12, '12 قسط'),
    ]
    
    installment_count = forms.ChoiceField(
        choices=INSTALLMENT_CHOICES,
        initial=1,
        label='عدد الأقساط',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'installment_count'})
    )
    
    first_installment_date = forms.DateField(
        required=False,
        label='تاريخ أول قسط',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'first_installment_date'
        })
    )
    
    class Meta:
        model = Student
        fields = [
            'full_name', 'phone', 'email', 'national_id', 'address',
            'branch', 'course', 'total_price', 'payment_method',
            'installment_count', 'first_installment_date', 'notes'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'الاسم بالكامل (ثلاثي أو رباعي)'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '01xxxxxxxxx'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@domain.com (اختياري)'
            }),
            'national_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '14 رقم'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'العنوان بالتفصيل'
            }),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'total_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select',
                'id': 'payment_method'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'أي ملاحظات خاصة (اختياري)'
            }),
        }
        labels = {
            'full_name': 'الاسم بالكامل',
            'phone': 'رقم الهاتف',
            'email': 'البريد الإلكتروني',
            'national_id': 'الرقم القومي',
            'address': 'العنوان',
            'branch': 'الفرع',
            'course': 'الدورة / الدبلومة',
            'total_price': 'المبلغ الإجمالي',
            'payment_method': 'طريقة الدفع',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user:
            from branches.models import Branch
            
            # إذا كان مدير إقليمي، عرض فروع منطقته فقط
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            
            # إذا كان أدمن أو سوبر يوزر، عرض كل الفروع النشطة
            elif user.is_superuser or user.user_type == 'admin':
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)

            # إذا كان موظف فرع أو مدير فرع
            else:
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch
                    self.fields['branch'].empty_label = None

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if full_name:
            full_name = full_name.strip()
            # التحقق من طول الاسم
            if len(full_name) < 6:
                raise forms.ValidationError('الاسم يجب أن يكون 6 أحرف على الأقل (ثلاثي أو رباعي)')
            # التحقق من عدم وجود أرقام
            if re.search(r'\d', full_name):
                raise forms.ValidationError('الاسم لا يجب أن يحتوي على أرقام')
            # التحقق من أن الاسم يحتوي على 3 كلمات على الأقل
            words = full_name.split()
            if len(words) < 3:
                raise forms.ValidationError('يرجى إدخال الاسم ثلاثياً أو رباعياً')
        return full_name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # إزالة المسافات والرموز
            phone = re.sub(r'\s+|-', '', phone)
            # التحقق من صحة الرقم المصري
            if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', phone):
                raise forms.ValidationError(
                    'رقم الهاتف غير صالح. يجب أن يبدأ بـ 01 ويكون 11 رقم (مثال: 01012345678)'
                )
            # التحقق من عدم تكرار الرقم
            existing = Student.objects.filter(phone=phone)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا الرقم مستخدم بالفعل لطالب آخر')
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            # التحقق من صحة البريد
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                raise forms.ValidationError('البريد الإلكتروني غير صالح')
            # التحقق من عدم التكرار
            existing = Student.objects.filter(email=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا البريد مستخدم بالفعل لطالب آخر')
        return email

    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        if national_id:
            national_id = national_id.strip()
            # التحقق من أن الرقم 14 رقم
            if not re.match(r'^\d{14}$', national_id):
                raise forms.ValidationError('الرقم القومي يجب أن يكون 14 رقم')
            # التحقق من صحة الرقم (الرقم الأول يجب أن يكون 2 أو 3 للمصريين)
            first_digit = national_id[0]
            if first_digit not in ['2', '3']:
                raise forms.ValidationError('الرقم القومي غير صالح (يجب أن يبدأ بـ 2 أو 3 للمصريين)')
            # التحقق من عدم التكرار
            existing = Student.objects.filter(national_id=national_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا الرقم القومي مسجل بالفعل')
        return national_id

    def clean_total_price(self):
        total_price = self.cleaned_data.get('total_price')
        if total_price is not None:
            if total_price <= 0:
                raise forms.ValidationError('المبلغ الإجمالي يجب أن يكون أكبر من صفر')
            if total_price > 1000000:
                raise forms.ValidationError('المبلغ الإجمالي كبير جداً، يرجى التحقق')
        return total_price

    def clean_address(self):
        address = self.cleaned_data.get('address')
        if address:
            address = address.strip()
            if len(address) < 10:
                raise forms.ValidationError('العنوان قصير جداً، يرجى إدخال عنوان مفصل')
        return address

    def clean_first_installment_date(self):
        first_installment_date = self.cleaned_data.get('first_installment_date')
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method == 'installment' and first_installment_date:
            today = date.today()
            # التاريخ يجب أن يكون اليوم أو في المستقبل
            if first_installment_date < today:
                raise forms.ValidationError('تاريخ أول قسط يجب أن يكون اليوم أو في المستقبل')
            # لا يمكن أن يتجاوز سنة من الآن
            max_date = today + timedelta(days=365)
            if first_installment_date > max_date:
                raise forms.ValidationError('تاريخ أول قسط لا يمكن أن يتجاوز سنة من الآن')
        return first_installment_date

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        installment_count = int(cleaned_data.get('installment_count', 1))
        first_installment_date = cleaned_data.get('first_installment_date')
        total_price = cleaned_data.get('total_price', 0)
        
        # التحقق من صحة بيانات الأقساط
        if payment_method == 'installment':
            if installment_count <= 1:
                self.add_error('installment_count', 'عند اختيار الدفع بالتقسيط، يجب اختيار عدد أقساط أكبر من 1')
            
            if not first_installment_date:
                self.add_error('first_installment_date', 'يرجى تحديد تاريخ أول قسط')
            
            # التحقق من المبلغ
            if total_price and installment_count > 0:
                installment_amount = total_price / installment_count
                if installment_amount < 100:
                    self.add_error('total_price', f'قيمة القسط ({installment_amount:.2f}) صغيرة جداً، يرجى زيادة المبلغ أو تقليل عدد الأقساط')
        
        # التحقق من اختيار الفرع والدورة
        branch = cleaned_data.get('branch')
        course = cleaned_data.get('course')
        
        if not branch:
            self.add_error('branch', 'يجب اختيار الفرع')
        
        if not course:
            self.add_error('course', 'يجب اختيار الدورة')
        elif branch and course:
            # التحقق من أن الدورة متاحة في هذا الفرع
            if not course.branches.filter(id=branch.id).exists():
                self.add_error('course', 'هذه الدورة غير متاحة في الفرع المختار')
        
        return cleaned_data
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        # تعيين قيم الأقساط
        installment_count = int(self.cleaned_data.get('installment_count', 1))
        total_price = self.cleaned_data.get('total_price', 0)
        
        student.installment_count = installment_count
        student.installment_amount = total_price / installment_count if installment_count > 0 else total_price
        
        if commit:
            student.save()
        
        return student


class NotificationSettingsForm(forms.ModelForm):
    """نموذج إعدادات الإشعارات"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'email_enabled', 'email_host', 'email_port',
            'email_use_tls', 'email_from_address',
            'whatsapp_enabled', 'whatsapp_api_url',
            'whatsapp_instance_id', 'reminder_2days_template', 'reminder_1day_template',
            'reminder_due_template', 'overdue_template', 'reminder_2days_before',
            'reminder_1day_before', 'reminder_on_due_date', 'send_overdue_notice',
            'contact_phone'
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_host': forms.TextInput(attrs={'class': 'form-control'}),
            'email_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'whatsapp_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'whatsapp_api_url': forms.URLInput(attrs={'class': 'form-control'}),
            'whatsapp_instance_id': forms.TextInput(attrs={'class': 'form-control'}),
            'reminder_2days_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reminder_1day_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reminder_due_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'overdue_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reminder_2days_before': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_1day_before': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_on_due_date': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_overdue_notice': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email_port(self):
        port = self.cleaned_data.get('email_port')
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError('رقم المنفذ يجب أن يكون بين 1 و 65535')
        return port

    def clean_contact_phone(self):
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            phone = re.sub(r'\s+|-', '', phone)
            if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', phone):
                raise forms.ValidationError('رقم الهاتف غير صالح')
        return phone
