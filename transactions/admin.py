from django.contrib import admin
from .admin_filters import DateRangeFilter
from .models import Income, Expense, DailySummary


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ['date', 'branch', 'party_name', 'income_type', 'amount', 'payment_method', 'payment_location', 'collected_by', 'created_at']
    list_filter = [
        ('created_at', DateRangeFilter),
        'created_at',
        'branch', 'income_type', 'payment_method', 'payment_location', 'date',
    ]
    search_fields = ['party_name', 'notes']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and request.user.branch:
            return qs.filter(branch=request.user.branch)
        return qs


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'branch', 'category', 'description', 'amount', 'created_by', 'created_at']
    list_filter = [
        ('created_at', DateRangeFilter),
        'created_at',
        'branch', 'category', 'date',
    ]
    search_fields = ['description', 'receipt_number']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser and request.user.branch:
            return qs.filter(branch=request.user.branch)
        return qs


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'branch', 'total_income', 'total_expenses', 'net_amount', 'achievement_percentage']
    list_filter = ['branch', 'date']
    readonly_fields = ['total_income', 'total_expenses', 'net_amount', 'achievement_percentage', 'new_registrations_count', 'installments_collected_count']
    date_hierarchy = 'date'
