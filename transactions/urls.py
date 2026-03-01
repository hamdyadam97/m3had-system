from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # الإيرادات
    path('income/', views.income_list, name='income_list'),
    path('income/add/', views.income_add, name='income_add'),
    path('income/<int:pk>/', views.income_detail, name='income_detail'),
    
    # المصروفات
    path('expense/', views.expense_list, name='expense_list'),
    path('expense/add/', views.expense_add, name='expense_add'),
    path('expense/<int:pk>/', views.expense_detail, name='expense_detail'),
    
    # الملخص اليومي
    path('daily-summary/', views.daily_summary, name='daily_summary'),
]
