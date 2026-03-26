from django import forms
from django.core.exceptions import ValidationError
from .enrollment_models import Enrollment
from .models import Student
from branches.models import Branch
from courses.models import Course


class EnrollmentForm(forms.ModelForm):
    """نموذج تسجيل طالب في دورة جديدة"""
    
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
    
    # سبب الانسحاب (لو كان التسجيل للتقوية)
    previous_enrollment_note = forms.CharField(
        required=False,
        label='ملاحظات على التسجيل السابق',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'مثال: انسحاب من الدورة السابقة بسبب...'
        })
    )
    
    class Meta:
        model = Enrollment
        fields = [
            'course', 'branch', 'enrollment_type', 'total_price',
            'payment_method', 'installment_count', 'first_installment_date',
            'start_date', 'notes', 'previous_enrollment_note'
        ]
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'enrollment_type': forms.Select(attrs={'class': 'form-select'}),
            'total_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select', 'id': 'payment_method'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, student=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.user = user
        
        # تحديد الفروع المتاحة حسب نوع المستخدم
        if user:
            if user.user_type == 'regional_manager':
                self.fields['branch'].queryset = user.managed_branches.filter(is_active=True)
            elif user.is_superuser or user.user_type == 'admin':
                self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
            else:
                if user.branch:
                    self.fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                    self.fields['branch'].initial = user.branch
        
        # تحديد الدورات المتاحة (كل الدورات النشطة)
        self.fields['course'].queryset = Course.objects.filter(is_active=True)
        
        # لو الطالب عنده تسجيل نشط، نمنع التسجيل في نفس الدورة (ماعدا التقوية)
        if student and student.has_active_enrollment():
            active_enrollment = student.get_active_enrollment()
            if active_enrollment:
                # نضيف تحذير في المساعدة
                self.fields['enrollment_type'].help_text = f"⚠️ الطالب مسجل حالياً في: {active_enrollment.course.name}"
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.student:
            raise ValidationError('لم يتم تحديد الطالب')

        if not self.student.can_enroll_in_new_course():
        # التحقق من إمكانية التسجيل
            if self.student.has_active_enrollment():
                active_enrollment = self.student.get_active_enrollment()
                enrollment_type = cleaned_data.get('enrollment_type')

                # لا يمكن التسجيل في دورة جديدة إلا لو كان نوع التسجيل تقوية أو إعادة
                # وفي هذه الحالة لازم يكون سحب من الدورة القديمة أولاً
                if enrollment_type == 'new':
                    raise ValidationError(
                        f'لا يمكن التسجيل في دورة جديدة لأن الطالب مسجل حالياً في: {active_enrollment.course.name}. '
                        'يجب إكمال الدورة الحالية أو الانسحاب منها أولاً.'
                    )
            if self.student.get_total_paid() <= 0:
                raise ValidationError(
                    f'عذراً! الطالب لديه حجز سابق لدورة ({self.student.course.name}) لم يتم سداده. يجب دفع القسط الأول أولاً.')
        
        # التحقق من بيانات الأقساط
        payment_method = cleaned_data.get('payment_method')
        installment_count = int(cleaned_data.get('installment_count', 1))
        first_installment_date = cleaned_data.get('first_installment_date')
        total_price = cleaned_data.get('total_price', 0)
        
        if payment_method == 'installment':
            if installment_count <= 1:
                raise ValidationError('عند اختيار الدفع بالتقسيط، يجب اختيار عدد أقساط أكبر من 1')
            
            if not first_installment_date:
                raise ValidationError('يرجى تحديد تاريخ أول قسط')
            
            cleaned_data['installment_count'] = installment_count
            cleaned_data['installment_amount'] = total_price / installment_count
        else:
            cleaned_data['installment_count'] = 1
            cleaned_data['installment_amount'] = total_price
        
        return cleaned_data
    
    def save(self, commit=True):
        enrollment = super().save(commit=False)
        enrollment.student = self.student
        
        # تعيين قيم الأقساط
        installment_count = int(self.cleaned_data.get('installment_count', 1))
        total_price = self.cleaned_data.get('total_price', 0)
        
        enrollment.installment_count = installment_count
        enrollment.installment_amount = total_price / installment_count if installment_count > 0 else total_price
        
        if commit:
            enrollment.save()
        
        return enrollment


class EnrollmentStatusForm(forms.Form):
    """نموذج تغيير حالة التسجيل (إكمال/انسحاب)"""
    
    ACTION_CHOICES = [
        ('complete', 'إكمال الدورة'),
        ('withdraw', 'الانسحاب من الدورة'),
        ('suspend', 'تعليق مؤقت'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label='الإجراء',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    reason = forms.CharField(
        required=False,
        label='السبب/الملاحظات',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'اكتب سبب الانسحاب أو أي ملاحظات إضافية...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        reason = cleaned_data.get('reason')
        
        if action == 'withdraw' and not reason:
            raise ValidationError('يرجى تحديد سبب الانسحاب')
        
        return cleaned_data
