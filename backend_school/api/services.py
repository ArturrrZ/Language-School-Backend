import logging

from django.db import transaction
from rest_framework import serializers

from .models import TrialLessonRequest
from .tasks import send_trial_request_notifications


OCCUPIED_TRIAL_LESSON_STATUSES = (
    TrialLessonRequest.Status.PENDING,
    TrialLessonRequest.Status.TEACHER_CONFIRMED,
    TrialLessonRequest.Status.ADMIN_APPROVED,
)


logger = logging.getLogger(__name__)


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
            lambda: send_trial_request_notifications.delay(trial_request_id)
        )
        logger.info('Queued trial lesson notifications for request #%s', trial_request_id)

    return trial_request