from django.urls import path
from . import views

app_name = 'branches'

urlpatterns = [
    path('', views.branch_list, name='branch_list'),
    path('<int:pk>/', views.branch_detail, name='branch_detail'),
    path('add/', views.branch_add, name='branch_add'),
    path('edit/<int:pk>/', views.branch_edit, name='branch_edit'),
    path('targets/add/', views.target_add, name='target_add'),
    path('targets/edit/<int:pk>/', views.target_edit, name='target_edit'),
]
