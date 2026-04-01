from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import (
    EmailAuthenticationForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    CustomPasswordChangeForm
)

app_name = 'accounts'

urlpatterns = [
    # المستخدمين
    path('', views.user_list, name='user_list'),
    path('add/', views.user_create, name='user_create'),
    path('<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('<int:pk>/toggle/', views.user_toggle_status, name='user_toggle_status'),
    
    # تسجيل الدخول بالبريد الإلكتروني
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=EmailAuthenticationForm
    ), name='login'),
    
    # تسجيل الخروج
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # نسيت كلمة المرور
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        form_class=CustomPasswordResetForm,
        success_url='/accounts/password-reset/done/'
    ), name='password_reset'),
    
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        form_class=CustomSetPasswordForm,
        success_url='/accounts/password-reset-complete/'
    ), name='password_reset_confirm'),
    
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # تغيير كلمة المرور (للمستخدمين المسجلين)
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html',
        form_class=CustomPasswordChangeForm,
        success_url='/accounts/password-change-done/'
    ), name='password_change'),
    
    path('password-change-done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html'
    ), name='password_change_done'),
    
    # الملف الشخصي
    path('profile/', views.profile, name='profile'),
    
    # التصدير والاستيراد
    path('export/users/excel/', views.export_users_excel, name='export_users_excel'),
    path('export/users/pdf/', views.export_users_pdf, name='export_users_pdf'),
    path('import/users/excel/', views.import_users_excel, name='import_users_excel'),
    
    # إشعارات النظام
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/api/get/', views.get_notifications, name='get_notifications'),
    path('notifications/<int:pk>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
