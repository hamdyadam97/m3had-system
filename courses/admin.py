from django.contrib import admin
from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'course_type', 'price', 'duration_days', 'is_active']
    list_filter = ['course_type', 'is_active', 'branches']
    search_fields = ['name', 'code']
    filter_horizontal = ['branches']
