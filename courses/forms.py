import re
from django import forms
from .models import Course


class CourseForm(forms.ModelForm):
    """نموذج إضافة/تعديل الدورة مع تحقق متقدم"""
    
    class Meta:
        model = Course
        fields = ['name', 'code', 'course_type', 'description', 'price', 'duration_days', 'branches', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم الدورة (مثال: دبلومة البرمجة المتكاملة)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'كود الدورة (مثال: DIP001)'
            }),
            'course_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'وصف تفصيلي للدورة...'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'عدد الأيام'
            }),
            'branches': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '5'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم الدورة / الدبلومة',
            'code': 'كود الدورة',
            'course_type': 'النوع',
            'description': 'الوصف',
            'price': 'السعر',
            'duration_days': 'المدة (بالأيام)',
            'branches': 'الفروع المتاحة',
            'is_active': 'نشطة',
        }
        help_texts = {
            'code': 'يجب أن يكون فريداً، حروف وأرقام فقط',
            'duration_days': 'عدد أيام الدراسة',
        }

    def clean_name(self):
        """التحقق من اسم الدورة"""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 5:
                raise forms.ValidationError('اسم الدورة قصير جداً (5 أحرف على الأقل)')
            if len(name) > 200:
                raise forms.ValidationError('اسم الدورة طويل جداً (الحد الأقصى 200 حرف)')
            # التحقق من أن الاسم لا يبدأ برقم
            if re.match(r'^\d', name):
                raise forms.ValidationError('اسم الدورة لا يجب أن يبدأ برقم')
        return name

    def clean_code(self):
        """التحقق من كود الدورة"""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            # التحقق من صيغة الكود
            if not re.match(r'^[A-Z0-9]+$', code):
                raise forms.ValidationError('كود الدورة يجب أن يحتوي على حروف إنجليزية وأرقام فقط')
            # التحقق من طول الكود
            if len(code) < 3:
                raise forms.ValidationError('كود الدورة قصير جداً (3 أحرف على الأقل)')
            if len(code) > 20:
                raise forms.ValidationError('كود الدورة طويل جداً (الحد الأقصى 20 حرف)')
            # التحقق من عدم التكرار
            existing = Course.objects.filter(code=code).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('هذا الكود مستخدم بالفعل لدورة أخرى!')
        return code

    def clean_price(self):
        """التحقق من السعر"""
        price = self.cleaned_data.get('price')
        if price is not None:
            if price < 0:
                raise forms.ValidationError('السعر لا يمكن أن يكون سالباً')
            if price > 1000000:
                raise forms.ValidationError('السعر كبير جداً (الحد الأقصى 1,000,000)')
            # التحقق من عدد الكسور العشرية
            price_str = str(price)
            if '.' in price_str:
                decimals = len(price_str.split('.')[1])
                if decimals > 2:
                    raise forms.ValidationError('السعر يجب أن يكون بحد أقصى منزلتين عشريتين')
        return price

    def clean_duration_days(self):
        """التحقق من المدة"""
        duration = self.cleaned_data.get('duration_days')
        if duration is not None:
            if duration < 1:
                raise forms.ValidationError('المدة يجب أن تكون يوم واحد على الأقل')
            if duration > 730:  # سنتين
                raise forms.ValidationError('المدة طويلة جداً (الحد الأقصى سنتين)')
        return duration

    def clean_description(self):
        """التحقق من الوصف"""
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
            if len(description) < 10:
                raise forms.ValidationError('الوصف قصير جداً (10 أحرف على الأقل)')
            if len(description) > 1000:
                raise forms.ValidationError('الوصف طويل جداً (الحد الأقصى 1000 حرف)')
            # التحقق من عدم وجود HTML خطر
            if re.search(r'<script|javascript:', description, re.IGNORECASE):
                raise forms.ValidationError('الوصف يحتوي على محتوى غير مسموح به')
        return description

    def clean_branches(self):
        """التحقق من الفروع"""
        branches = self.cleaned_data.get('branches')
        if not branches:
            raise forms.ValidationError('يجب اختيار فرع واحد على الأقل')
        if branches.count() > 50:
            raise forms.ValidationError('لا يمكن اختيار أكثر من 50 فرع')
        return branches

    def clean(self):
        """التحقق المتقاطع"""
        cleaned_data = super().clean()
        
        course_type = cleaned_data.get('course_type')
        duration_days = cleaned_data.get('duration_days')
        
        # التحقق من تطابق المدة مع نوع الدورة
        if course_type and duration_days:
            if course_type == 'diploma':
                # الدبلومة يجب أن تكون 90 يوم على الأقل
                if duration_days < 90:
                    self.add_error('duration_days', 'الدبلومة يجب أن تكون 90 يوم على الأقل (3 أشهر)')
            elif course_type == 'course':
                # الدورة يمكن أن تكون أقل
                if duration_days > 180:
                    self.add_warning = True  # تحذير فقط
        
        return cleaned_data
