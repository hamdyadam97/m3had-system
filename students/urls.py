from django.urls import path
from . import views
from .enrollment_views import (
    enrollment_list, enrollment_add, 
    enrollment_change_status, enrollment_detail
)

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('add/', views.student_add, name='student_add'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('<int:student_pk>/installments/', views.installment_plan_detail, name='installment_plan'),
    
    # إدارة التسجيلات في الدورات (Enrollments)
    path('<int:student_pk>/enrollments/', enrollment_list, name='enrollment_list'),
    path('<int:student_pk>/enrollments/add/', enrollment_add, name='enrollment_add'),
    path('enrollments/<int:enrollment_pk>/', enrollment_detail, name='enrollment_detail'),
    path('enrollments/<int:enrollment_pk>/change-status/', enrollment_change_status, name='enrollment_change_status'),

    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),

    path('ajax/get-courses-by-branch/', views.get_courses_by_branch, name='get_courses_by_branch'),

    # إعدادات الإشعارات
    path('notification-settings/', views.notification_settings, name='notification_settings'),
    path('notification-logs/', views.notification_logs, name='notification_logs'),
]
