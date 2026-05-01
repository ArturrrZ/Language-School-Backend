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


def _send_trial_status_student_email(trial_request: TrialLessonRequest, old_status: str | None = None) -> None:
    student_email = trial_request.student.email
    if not student_email:
        logger.info('Student email is empty for trial request #%s. Student email skipped.', trial_request.id)
        return

    origin = getattr(settings, 'FRONT_SITE_ORIGIN', 'http://127.0.0.1:3000').rstrip('/')
    request_url = f'{origin}/api/trial-lessons/my/'
    teacher_name = trial_request.teacher.user.get_full_name() or trial_request.teacher.user.username
    context = {
        'trial_request_id': trial_request.id,
        'teacher_name': teacher_name,
        'student_name': trial_request.student.get_full_name() or trial_request.student.username,
        'start_at': trial_request.start_at,
        'end_at': trial_request.end_at,
        'old_status': old_status,
        'new_status': trial_request.status,
        'old_status_label': dict(TrialLessonRequest.Status.choices).get(old_status, '—') if old_status else '—',
        'new_status_label': trial_request.get_status_display(),
        'admin_note': trial_request.admin_note,
        'teacher_note': trial_request.teacher_note,
        'request_url': request_url,
    }

    html_message = render_to_string('emails/trial_request_student_status.html', context)
    note_lines = []
    if context['admin_note']:
        note_lines.append(f'Admin note: {context["admin_note"]}')
    if context['teacher_note']:
        note_lines.append(f'Teacher note: {context["teacher_note"]}')

    notes_block = f'\n{"\n".join(note_lines)}' if note_lines else ''

    plain_message = (
        f'Trial lesson request #{trial_request.id} status update: '
        f'{context["old_status_label"]} -> {context["new_status_label"]}.\n'
        f'{notes_block}\n'
        f'Check details: {request_url}'
    )

    send_mail(
        subject=f'Update on Trial Lesson Request #{trial_request.id}: {context["new_status_label"]}',
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[student_email],
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


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 5},
)
def send_trial_status_email(self, trial_request_id: int, old_status: str | None = None) -> str:
    trial_request = (
        TrialLessonRequest.objects
        .select_related('teacher__user', 'student')
        .filter(id=trial_request_id)
        .first()
    )
    if not trial_request:
        logger.warning('TrialLessonRequest #%s not found. Student status email skipped.', trial_request_id)
        return 'not_found'

    _send_trial_status_student_email(trial_request, old_status=old_status)
    logger.info('Student status email sent for TrialLessonRequest #%s', trial_request_id)
    return 'ok'