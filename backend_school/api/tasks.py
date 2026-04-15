import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import TrialLessonRequest


logger = logging.getLogger(__name__)


def _send_trial_lesson_admin_email(trial_request: TrialLessonRequest) -> None:
    admin_email = settings.TRIAL_REQUEST_NOTIFICATION_EMAIL
    if not admin_email:
        logger.info('TRIAL_REQUEST_NOTIFICATION_EMAIL is empty. Admin email skipped.')
        return

    origin = getattr(settings, 'SITE_ORIGIN', 'http://127.0.0.1:8000')
    admin_url = f'{origin}/admin/api/triallessonrequest/{trial_request.id}/change/'

    context = {
        'trial_request_id': trial_request.id,
        'student_name': trial_request.student.get_full_name() or trial_request.student.username,
        'teacher_name': trial_request.teacher.user.get_full_name() or trial_request.teacher.user.username,
        'start_at': trial_request.start_at,
        'end_at': trial_request.end_at,
        'admin_url': admin_url,
        'admin_home': f'{origin}/admin/',
    }
    html_message = render_to_string('emails/trial_request_admin.html', context)

    send_mail(
        subject=f'New trial lesson request #{trial_request.id} - Admin Review',
        message=f'Trial lesson request #{trial_request.id}',
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[admin_email],
        fail_silently=False,
    )


def _send_trial_lesson_teacher_email(trial_request: TrialLessonRequest) -> None:
    teacher_email = trial_request.teacher.user.email
    if not teacher_email:
        logger.info('Teacher email is empty for trial request #%s. Teacher email skipped.', trial_request.id)
        return

    admin_email = settings.TRIAL_REQUEST_NOTIFICATION_EMAIL
    context = {
        'trial_request_id': trial_request.id,
        'student_name': trial_request.student.get_full_name() or trial_request.student.username,
        'start_at': trial_request.start_at,
        'end_at': trial_request.end_at,
        'student_note': trial_request.student_note,
        'admin_email': admin_email,
        'admin_phone': None,
    }
    html_message = render_to_string('emails/trial_request_teacher.html', context)

    send_mail(
        subject=f'New Trial Lesson Request #{trial_request.id}',
        message=f'Trial lesson request #{trial_request.id}',
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[teacher_email],
        fail_silently=False,
    )


@shared_task
def test_print_message():
    print('Hello from Celery task!')

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 5},
)
def send_trial_request_notifications(self, trial_request_id: int) -> str:
    trial_request = (
        TrialLessonRequest.objects
        .select_related('teacher__user', 'student')
        .filter(id=trial_request_id)
        .first()
    )
    if not trial_request:
        logger.warning('TrialLessonRequest #%s not found. Notifications skipped.', trial_request_id)
        return 'not_found'

    _send_trial_lesson_admin_email(trial_request)
    _send_trial_lesson_teacher_email(trial_request)

    logger.info('Notifications sent for TrialLessonRequest #%s', trial_request_id)
    return 'ok'