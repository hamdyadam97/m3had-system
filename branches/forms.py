import re
from django import forms
from .models import Branch, BranchTarget


class BranchForm(forms.ModelForm):
    """نموذج إضافة/تعديل الفرع مع تحقق متقدم"""
    
    class Meta:
        model = Branch
        fields = ['name', 'code', 'address', 'phone', 'email', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم الفرع (مثال: فرع القاهرة الرئيسي)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'كود الفرع (مثال: CAI01)'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'العنوان بالتفصيل'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '02xxxxxxxx'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'branch@example.com'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم الفرع',
            'code': 'كود الفرع',
            'address': 'العنوان',
            'phone': 'رقم الهاتف',
            'email': 'البريد الإلكتروني',
            'is_active': 'نشط',
        }
        help_texts = {
            'code': 'يجب أن يكون فريداً، حروف وأرقام فقط',
        }

    def clean_name(self):
        """التحقق من اسم الفرع"""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 3:
                raise forms.ValidationError('اسم الفرع قصير جداً (3 أحرف على الأقل)')
            if len(name) > 100:
                raise forms.ValidationError('اسم الفرع طويل جداً (الحد الأقصى 100 حرف)')
            # التحقق من أن الاسم لا يحتوي على أرقام فقط
            if re.match(r'^\d+$', name):
                raise forms.ValidationError('اسم الفرع لا يمكن أن يكون أرقام فقط')
        return name

    def clean_code(self):
        """التحقق من كود الفرع"""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            # التحقق من صيغة الكود (حروف وأرقام فقط)
            if not re.match(r'^[A-Z0-9]+$', code):
                raise forms.ValidationError('كود الفرع يجب أن يحتوي على حروف إنجليزية وأرقام فقط')
            # التحقق من طول الكود
            if len(code) < 3:
                raise forms.ValidationError('كود الفرع قصير جداً (3 أحرف على الأقل)')
            if len(code) > 10:
                raise forms.ValidationError('كود الفرع طويل جداً (الحد الأقصى 10 أحرف)')
            # التحقق من عدم التكرار
            if Branch.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError('هذا الكود مستخدم بالفعل لفرع آخر!')
        return code

    def clean_phone(self):
        """التحقق من رقم الهاتف"""
        phone = self.cleaned_data.get('phone')
        if phone:
            phone = re.sub(r'\s+|-', '', phone)
            # السماح بأرقام أرضية (02xxxxxxx) أو محمولة (01xxxxxxxxx)
            if re.match(r'^02\d{8,9}$', phone):
                # رقم أرضي صحيح
                pass
            elif re.match(r'^01[0-2,5]{1}[0-9]{8}$', phone):
                # رقم محمول صحيح
                pass
            else:
                raise forms.ValidationError(
                    'رقم الهاتف غير صالح. يجب أن يكون رقم أرضي (02xxxxxxxx) أو محمول (01xxxxxxxxx)'
                )
        return phone

    def clean_email(self):
        """التحقق من البريد الإلكتروني"""
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            # التحقق من صيغة البريد
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                raise forms.ValidationError('البريد الإلكتروني غير صالح')
            # التحقق من عدم التكرار
            existing = Branch.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا البريد الإلكتروني مستخدم بالفعل لفرع آخر')
        return email

    def clean_address(self):
        """التحقق من العنوان"""
        address = self.cleaned_data.get('address')
        if address:
            address = address.strip()
            if len(address) < 10:
                raise forms.ValidationError('العنوان قصير جداً (10 أحرف على الأقل)')
            if len(address) > 500:
                raise forms.ValidationError('العنوان طويل جداً (الحد الأقصى 500 حرف)')
        return address


class BranchTargetForm(forms.ModelForm):
    """نموذج إضافة/تعديل هدف الفرع"""
    
    class Meta:
        model = BranchTarget
        fields = ['branch', 'year', 'month', 'amount']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2050'
            }),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
        }
        labels = {
            'branch': 'الفرع',
            'year': 'السنة',
            'month': 'الشهر',
            'amount': 'المبلغ المستهدف',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تحديد السنة الحالية كقيمة افتراضية
        self.fields['year'].initial = date.today().year

    def clean_year(self):
        """التحقق من السنة"""
        year = self.cleaned_data.get('year')
        if year:
            current_year = date.today().year
            if year < current_year - 1:
                raise forms.ValidationError('السنة قديمة جداً')
            if year > current_year + 5:
                raise forms.ValidationError('السنة بعيدة جداً (الحد الأقصى 5 سنوات)')
        return year

    def clean_amount(self):
        """التحقق من المبلغ"""
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= 0:
                raise forms.ValidationError('المبلغ يجب أن يكون أكبر من صفر')
            if amount > 100000000:  # 100 مليون
                raise forms.ValidationError('المبلغ كبير جداً')
        return amount

    def clean(self):
        """التحقق المتقاطع"""
        cleaned_data = super().clean()
        branch = cleaned_data.get('branch')
        year = cleaned_data.get('year')
        month = cleaned_data.get('month')

        # التحقق من عدم تكرار الشهر لنفس الفرع في نفس السنة
        if branch and year and month:
            exists = BranchTarget.objects.filter(
                branch=branch,
                year=year,
                month=month
            ).exclude(pk=self.instance.pk).exists()

            if exists:
                month_name = dict(BranchTarget.MONTH_CHOICES).get(month)
                raise forms.ValidationError(
                    f'هدف شهر {month_name} لسنة {year} مضاف بالفعل لهذا الفرع!'
                )

        # التحقق من أن الشهر والسنة في المستقبل
        if year and month:
            from datetime import date
            try:
                target_date = date(year, month, 1)
                # السماح بتحديد أهداف حتى سنة قادمة
                max_date = date.today().replace(year=date.today().year + 1, month=12, day=31)
                if target_date > max_date:
                    raise forms.ValidationError('لا يمكن تحديد هدف لتاريخ بعيد جداً')
            except ValueError:
                raise forms.ValidationError('تاريخ غير صالح')

        return cleaned_data


# استيراد date للاستخدام في clean
from datetime import date
