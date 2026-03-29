from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('add/', views.user_create, name='user_create'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/toggle/', views.user_toggle_status, name='user_toggle_status'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('export/users/excel/', views.export_users_excel, name='export_users_excel'),
    path('export/users/pdf/', views.export_users_pdf, name='export_users_pdf'),
    path('import/users/excel/', views.import_users_excel, name='import_users_excel'),
    
    # إشعارات النظام
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/api/get/', views.get_notifications, name='get_notifications'),
    path('notifications/<int:pk>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
