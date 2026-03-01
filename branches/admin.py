from django.contrib import admin
from .models import Branch,BranchTarget


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'phone']
    readonly_fields = ['created_at']


@admin.register(BranchTarget)
class BranchTargetAdmin(admin.ModelAdmin):
    list_display = ('branch', 'year', 'month', 'amount')
    list_filter = ('year', 'month', 'branch')
    search_fields = ('branch__name',)