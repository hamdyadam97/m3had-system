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
    path('export/excel/', views.export_branches_excel, name='export_branches_excel'),
    path('import/excel/', views.import_branches_excel, name='import_branches_excel'),
    path('export/pdf/', views.export_branches_pdf, name='export_branches_pdf'), # السطر المطلوب
]
