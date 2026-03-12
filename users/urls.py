from django.urls import path

from .views import UserProfileView

app_name = 'users'

urlpatterns = [
    path('profil/<int:pk>/', UserProfileView.as_view(), name='profile'),
]
