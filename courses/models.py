from django.db import models
from branches.models import Branch


class Course(models.Model):
    COURSE_TYPE_CHOICES = [
        ('diploma', 'دبلومة'),
        ('course', 'دورة'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='اسم الدورة/الدبلومة')
    code = models.CharField(max_length=20, unique=True, verbose_name='كود الدورة')
    course_type = models.CharField(max_length=10, choices=COURSE_TYPE_CHOICES, verbose_name='النوع')
    description = models.TextField(blank=True, verbose_name='الوصف')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='السعر')
    duration_days = models.PositiveIntegerField(default=30, verbose_name='المدة (بالأيام)')
    branches = models.ManyToManyField(Branch, related_name='courses', verbose_name='الفروع المتاحة')
    is_active = models.BooleanField(default=True, verbose_name='نشطة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'دورة/دبلومة'
        verbose_name_plural = 'الدورات والدبلومات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_course_type_display()})"
    
    def get_registered_students_count(self, branch=None):
        """عدد الطلاب المسجلين في الدورة"""
        from students.models import Student
        queryset = Student.objects.filter(course=self)
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset.count()
    
    def get_total_collected(self, branch=None):
        """إجمالي المحصل للدورة"""
        from transactions.models import Income
        queryset = Income.objects.filter(course=self)
        if branch:
            queryset = queryset.filter(branch=branch)
        return sum(income.amount for income in queryset)
