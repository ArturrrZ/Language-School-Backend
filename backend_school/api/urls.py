from django.urls import path
from . import views

urlpatterns = [
    # Define your API endpoints here
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/refresh/', views.RefreshTokenView.as_view(), name='token_refresh'),
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/<int:teacher_id>/availability/', views.TeacherAvailabilityView.as_view(), name='teacher_availability'),
    path('trial-lessons/', views.TrialLessonRequestCreateView.as_view(), name='trial_lesson_create'),
    path('trial-lessons/my/', views.MyTrialLessonRequestListView.as_view(), name='my_trial_lessons'),
]