from django import forms

from branches.models import Branch
from .models import Income, Expense
from students.models import Student
from courses.models import Course


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = [
            'date', 'income_type', 'student', 'course', 'amount',
            'payment_method', 'payment_location', 'bank_account_number', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'income_type': forms.Select(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_location': forms.Select(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية الطلاب حسب فرع المستخدم
        if self.user and self.user.branch:
            self.fields['student'].queryset = Student.objects.filter(
                branch=self.user.branch, is_active=True
            )
            self.fields['course'].queryset = Course.objects.filter(
                branches=self.user.branch, is_active=True
            )





class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['branch', 'category', 'amount', 'date', 'notes', 'receipt_image']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_image': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # لو المستخدم مدير فرع، نخفي اختيار الفرع لأنه سيتسجل تلقائياً
        if user and user.branch:
            self.fields['branch'].widget = forms.HiddenInput()
            self.fields['branch'].required = False
        else:
            # لو سوبر يوزر، نظهر اختيار الفروع كلها
            self.fields['branch'].queryset = Branch.objects.all()
            self.fields['branch'].widget.attrs.update({'class': 'form-select'})