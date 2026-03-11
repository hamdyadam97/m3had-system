from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('add/', views.student_add, name='student_add'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('<int:student_pk>/installments/', views.installment_plan_detail, name='installment_plan'),
    
    # إعدادات الإشعارات
    path('notification-settings/', views.notification_settings, name='notification_settings'),
    path('notification-logs/', views.notification_logs, name='notification_logs'),
]
