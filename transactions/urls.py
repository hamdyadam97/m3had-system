from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # الإيرادات
    path('income/', views.income_list, name='income_list'),
    path('income/excel-style/', views.excel_style_transaction, name='excel_style_transaction'),
    path('income/import-excel/', views.excel_import, name='excel_import'),
    path('income/import-excel/revalidate/', views.excel_import_revalidate, name='excel_import_revalidate'),
    path('income/import-excel/commit/', views.excel_import_commit, name='excel_import_commit'),
    path('income/import-status/<str:task_id>/', views.import_task_status, name='import_task_status'),
    path('income/import-status-api/<str:task_id>/', views.task_status_api, name='task_status_api'),
    path('income/<int:pk>/', views.income_detail, name='income_detail'),

    # الطلاب
    path('students/', views.student_list, name='student_list'),

    # المصروفات
    path('expense/', views.expense_list, name='expense_list'),
    path('expense/excel-style/', views.excel_style_expense, name='excel_style_expense'),
    path('expense/import-excel/', views.excel_import_expense, name='excel_import_expense'),
    path('expense/import-excel/revalidate/', views.excel_import_expense_revalidate, name='excel_import_expense_revalidate'),
    path('expense/import-excel/commit/', views.excel_import_expense_commit, name='excel_import_expense_commit'),
    path('expense/<int:pk>/', views.expense_detail, name='expense_detail'),
    
    # الملخص اليومي
    path('daily-summary/', views.daily_summary, name='daily_summary'),
]
