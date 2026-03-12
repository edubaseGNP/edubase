from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('predmety/', views.subject_preferences, name='subject_preferences'),
    path('notifikace/', views.notifications_list, name='notifications'),
    path('statistiky/', views.teacher_statistics, name='statistics'),
    path('profil/', views.profile, name='profile'),
]
