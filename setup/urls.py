from django.urls import path
from . import views

app_name = 'setup'

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('school/', views.school, name='school'),
    path('admin-account/', views.admin_account, name='admin_account'),
    path('done/', views.done, name='done'),
]
