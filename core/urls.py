from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('predmety/', views.subject_preferences, name='subject_preferences'),
]
