from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Reports Dashboard
    path('', views.reports_dashboard, name='reports_dashboard'),
    
    # Basic Reports
    path('daily/', views.daily_report, name='daily_report'),
    path('monthly/', views.monthly_report, name='monthly_report'),
    
    # Advanced Reports - Branches
    path('branches/', views.branches_report, name='branches_report'),
    
    # Advanced Reports - Employees
    path('employees/', views.employees_report, name='employees_report'),
    
    # Advanced Reports - Courses & Diplomas
    path('courses/', views.courses_report, name='courses_report'),
    path('diplomas/', views.diplomas_report, name='diplomas_report'),
    
    # Advanced Reports - Time Analysis
    path('time-analysis/', views.time_analysis_report, name='time_analysis'),
    
    # KPIs Dashboard
    path('kpis/', views.kpis_dashboard, name='kpis_dashboard'),
]
