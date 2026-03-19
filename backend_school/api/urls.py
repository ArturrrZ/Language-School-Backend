from django.urls import path
from . import views

urlpatterns = [
    # Define your API endpoints here
    path('test/', views.TestView.as_view(), name='test'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/refresh/', views.RefreshTokenView.as_view(), name='token_refresh'),
]