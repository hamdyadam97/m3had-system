from django import forms
from .models import Student
from .notification_models import NotificationSettings


class StudentForm(forms.ModelForm):
    """نموذج إضافة/تعديل الطالب مع خيارات التقسيط"""
    
    # خيارات عدد الأقساط
    INSTALLMENT_CHOICES = [
        (1, 'دفعة واحدة (كامل المبلغ)'),
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
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'total_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select', 'id': 'payment_method'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user:
            from branches.models import Branch
            
            # إذا كان مدير إقليمي، عرض فروع منطقته فقط
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.all()
            
            # إذا كان أدمن أو سوبر يوزر، عرض كل الفروع النشطة
            elif user.is_superuser or user.user_type == 'admin':
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)

            # إذا كان موظف فرع أو مدير فرع (وليس أدمن عام)
            else:
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch
                    # بدلاً من disabled، نجعل الحقل غير قابل للتعديل مع بقاء قيمته مرسلة
                    # أو نتركه كما هو لأن الـ Queryset يحتوي على فرع واحد فقط أصلاً
                    self.fields['branch'].empty_label = None  # لإزالة خيار "---------"
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        installment_count = int(cleaned_data.get('installment_count', 1))
        first_installment_date = cleaned_data.get('first_installment_date')
        total_price = cleaned_data.get('total_price', 0)
        
        # التحقق من صحة بيانات الأقساط
        if payment_method == 'installment':
            if installment_count <= 1:
                raise forms.ValidationError('عند اختيار الدفع بالتقسيط، يجب اختيار عدد أقساط أكبر من 1')
            
            if not first_installment_date:
                raise forms.ValidationError('يرجى تحديد تاريخ أول قسط')
            
            # حساب قيمة القسط
            cleaned_data['installment_count'] = installment_count
            cleaned_data['installment_amount'] = total_price / installment_count
        else:
            cleaned_data['installment_count'] = 1
            cleaned_data['installment_amount'] = total_price
        
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
            'email_enabled', 'email_host', 'email_port', 'email_host_user',
            'email_host_password', 'email_use_tls', 'email_from_address',
            'whatsapp_enabled', 'whatsapp_api_key', 'whatsapp_api_url',
            'whatsapp_instance_id', 'reminder_2days_template', 'reminder_1day_template',
            'reminder_due_template', 'overdue_template', 'reminder_2days_before',
            'reminder_1day_before', 'reminder_on_due_date', 'send_overdue_notice',
            'contact_phone'
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_host': forms.TextInput(attrs={'class': 'form-control'}),
            'email_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_host_user': forms.TextInput(attrs={'class': 'form-control'}),
            'email_host_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'email_use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'whatsapp_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'whatsapp_api_key': forms.TextInput(attrs={'class': 'form-control'}),
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
