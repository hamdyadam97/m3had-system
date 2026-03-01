from django import forms
from .models import Course

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'course_type', 'description', 'price', 'duration_days', 'branches', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'branches': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Validation للتأكد من أن الكود فريد (Unique) حتى لو كانت الدورة محذوفة سوفت
    def clean_code(self):
        code = self.cleaned_data.get('code').upper()
        instance = self.instance
        if Course.objects.filter(code=code).exclude(pk=instance.pk).exists():
            raise forms.ValidationError("هذا الكود مستخدم بالفعل لدورة أخرى!")
        return code