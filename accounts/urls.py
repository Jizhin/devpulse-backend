from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # User
    path('me/', views.get_current_user, name='current-user'),
    path('me/update/', views.update_profile, name='update-profile'),
    path('me/change-password/', views.change_password, name='change-password'),
]