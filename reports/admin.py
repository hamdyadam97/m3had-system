from django.contrib import admin
from .models import MonthlyReport, CourseReport, EmployeeReport


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ['branch', 'year', 'month', 'monthly_target', 'total_income', 'achievement_percentage', 'profit']
    list_filter = ['branch', 'year', 'month']
    readonly_fields = ['total_income', 'total_expenses', 'net_amount', 'profit', 'achievement_percentage']


@admin.register(CourseReport)
class CourseReportAdmin(admin.ModelAdmin):
    list_display = ['course', 'branch', 'date', 'daily_registrations', 'daily_income', 'monthly_income']
    list_filter = ['branch', 'course', 'date']


@admin.register(EmployeeReport)
class EmployeeReportAdmin(admin.ModelAdmin):
    list_display = ['employee', 'branch', 'date', 'registrations_count', 'installments_count', 'total_collected']
    list_filter = ['branch', 'date']
