from django.urls import path
from . import views

urlpatterns = [
    # Define your API endpoints here
    #auth endpoints
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    #get all teachers and their availability
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/<int:teacher_id>/availability/', views.TeacherAvailabilityView.as_view(), name='teacher_availability'),
    #trial lesson and free consultation endpoints
    path('trial-lessons/', views.TrialLessonRequestCreateView.as_view(), name='trial_lesson_create'),
    path('trial-lessons/my/', views.MyTrialLessonRequestListView.as_view(), name='my_trial_lessons'),
    #teacher endpoints
    path('teacher/trial-lessons/', views.TeacherTrialLessonRequestListView.as_view(), name='teacher_trial_lessons'),
    path('teacher/trial-lessons/<int:trial_request_id>/update/', views.TeacherTrialLessonRequestUpdateView.as_view(), name='teacher_trial_lesson_update'),
    path('trial-lessons/<int:trial_request_id>/cancel/', views.StudentTrialLessonCancelView.as_view(), name='student_trial_lesson_cancel'),
    #free consultation endpoints
    path('free-consultations/', views.FreeConsultationRequestCreateView.as_view(), name='free_consultation_create'),
]