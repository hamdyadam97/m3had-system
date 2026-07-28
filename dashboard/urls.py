from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/data/', views.dashboard_data_api, name='dashboard_data_api'),
    path('branch/<int:branch_id>/', views.branch_dashboard, name='branch_dashboard'),
]
