from django import forms
from .models import Student
from courses.models import Course


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'full_name', 'phone', 'email', 'national_id', 'address',
            'course', 'total_price', 'payment_method', 'payment_location',
            'installment_count', 'bank_account_number', 'notes'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'total_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_location': forms.Select(attrs={'class': 'form-control'}),
            'installment_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية الدورات حسب فرع المستخدم
        if self.user and self.user.branch:
            self.fields['course'].queryset = Course.objects.filter(
                branches=self.user.branch, is_active=True
            )
