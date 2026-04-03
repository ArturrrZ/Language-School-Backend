import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from rest_framework import serializers

from .models import TrialLessonRequest


OCCUPIED_TRIAL_LESSON_STATUSES = (
    TrialLessonRequest.Status.PENDING,
    TrialLessonRequest.Status.TEACHER_CONFIRMED,
    TrialLessonRequest.Status.ADMIN_APPROVED,
)


logger = logging.getLogger(__name__)

#later to redis or celery tasks
def send_trial_lesson_admin_email(trial_request_id: int, student, teacher, start_at, end_at) -> None:
    """Send email to admin with manage button."""
    admin_email = settings.TRIAL_REQUEST_NOTIFICATION_EMAIL
    if not admin_email:
        return
    
    origin = settings.SITE_ORIGIN if hasattr(settings, 'SITE_ORIGIN') else 'http://127.0.0.1:8000'
    admin_url = f'{origin}/admin/api/triallessonrequest/{trial_request_id}/change/'
    
    context = {
        'trial_request_id': trial_request_id,
        'student_name': student.get_full_name() or student.username,
        'teacher_name': teacher.user.get_full_name() or teacher.user.username,
        'start_at': start_at,
        'end_at': end_at,
        'admin_url': admin_url,
        'admin_home': f"{origin}/admin/",
    }
    
    html_message = render_to_string('emails/trial_request_admin.html', context)
    
    try:
        send_mail(
            subject=f'New trial lesson request #{trial_request_id} - Admin Review',
            message=f'Trial lesson request #{trial_request_id}',
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
        )
        print(f'✓ Admin email sent for trial request #{trial_request_id} to {admin_email}')
    except Exception as e:
        print(f'✗ Failed to send admin email for trial request #{trial_request_id}: {e}')

#later to redis or celery tasks
def send_trial_lesson_teacher_email(trial_request_id: int, student, teacher, start_at, end_at, student_note, admin_phone: str = None) -> None:
    """Send email to teacher with lesson details and reminder to contact admin."""
    teacher_email = teacher.user.email
    admin_email = settings.TRIAL_REQUEST_NOTIFICATION_EMAIL
    if not teacher_email:
        return
    
    context = {
        'trial_request_id': trial_request_id,
        'student_name': student.get_full_name() or student.username,
        'start_at': start_at,
        'end_at': end_at,
        'student_note': student_note,
        'admin_email': admin_email,
        'admin_phone': admin_phone,
    }

    html_message = render_to_string('emails/trial_request_teacher.html', context)
    
    try:
        send_mail(
            subject=f'New Trial Lesson Request #{trial_request_id}',
            message=f'Trial lesson request #{trial_request_id}',
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[teacher_email],
            fail_silently=False,
        )
        print(f'✓ Teacher email sent for trial request #{trial_request_id} to {teacher_email}')
    except Exception as e:
        print(f'✗ Failed to send teacher email for trial request #{trial_request_id}: {e}')


def create_trial_lesson_request(*, student, teacher, start_at, end_at, student_note=''):
    with transaction.atomic():
        # Финальная защита от гонки.
        overlap_exists = TrialLessonRequest.objects.select_for_update().filter(
            teacher=teacher,
            status__in=OCCUPIED_TRIAL_LESSON_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        ).exists()

        if overlap_exists:
            raise serializers.ValidationError({
                'start_at': 'Teacher already has a lesson in this time range.'
            })

        trial_request = TrialLessonRequest.objects.create(
            student=student,
            teacher=teacher,
            start_at=start_at,
            end_at=end_at,
            student_note=student_note,
            status=TrialLessonRequest.Status.PENDING,
        )

        trial_request_id = trial_request.id

        transaction.on_commit(
            lambda: send_trial_lesson_admin_email(trial_request_id, student=student, teacher=teacher, start_at=start_at, end_at=end_at)
        )
        transaction.on_commit(
            lambda: send_trial_lesson_teacher_email(trial_request_id, student=student, teacher=teacher, start_at=start_at, end_at=end_at, student_note=student_note)
        )

    return trial_request