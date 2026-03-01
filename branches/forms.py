# branches/forms.py
from .models import Branch
from django import forms
from .models import BranchTarget

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'code', 'address', 'phone', 'email', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم الفرع'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'كود الفرع (مثال: CAI01)'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Validation مخصص للكود
    def clean_code(self):
        code = self.cleaned_data.get('code').upper()
        if Branch.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("هذا الكود مستخدم بالفعل لفرع آخر!")
        return code


    # Validation مخصص للهدف الشهري
    def clean_monthly_target(self):
        target = self.cleaned_data.get('monthly_target')
        if target <= 0:
            raise forms.ValidationError("يجب أن يكون الهدف الشهري أكبر من صفر!")
        return target





class BranchTargetForm(forms.ModelForm):
    class Meta:
        model = BranchTarget
        fields = ['branch', 'year', 'month', 'amount']
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'month': forms.Select(attrs={'class': 'form-control form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    def clean(self):
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
            ).exists()

            # في حالة التعديل، يجب استثناء السجل الحالي (self.instance)
            if self.instance.pk:
                exists = BranchTarget.objects.filter(
                    branch=branch,
                    year=year,
                    month=month
                ).exclude(pk=self.instance.pk).exists()

            if exists:
                month_name = dict(BranchTarget.MONTH_CHOICES).get(month)
                raise forms.ValidationError(
                    f"خطأ: هدف شهر {month_name} لسنة {year} مضاف بالفعل لهذا الفرع!"
                )

        return cleaned_data