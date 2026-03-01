from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('branch/<int:branch_id>/', views.branch_dashboard, name='branch_dashboard'),
]
