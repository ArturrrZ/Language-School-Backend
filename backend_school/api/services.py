import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
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
        # Final race protection and validations.
        # Ensure start/end are in the future (defensive; serializer should already validate)
        if start_at <= timezone.now():
            raise serializers.ValidationError({'start_at': 'Trial lesson must be in the future.'})

        # Respect buffer minutes when checking overlaps so student cannot book
        # into buffer zones around existing bookings.
        buffer_minutes = getattr(settings, 'TRIAL_LESSON_BUFFER_MINUTES', 15)
        buffer_delta = timedelta(minutes=buffer_minutes)
        check_start = start_at - buffer_delta
        check_end = end_at + buffer_delta

        # Lock relevant rows to avoid race conditions.
        overlap_exists = TrialLessonRequest.objects.select_for_update().filter(
            teacher=teacher,
            status__in=OCCUPIED_TRIAL_LESSON_STATUSES,
            start_at__lt=check_end,
            end_at__gt=check_start,
        ).exists()

        if overlap_exists:
            raise serializers.ValidationError({
                'start_at': 'Teacher already has a lesson in this time range.'
            })

        # Prevent student from booking overlapping lessons (with buffer) on their side as well.
        student_overlap = TrialLessonRequest.objects.select_for_update().filter(
            student=student,
            status__in=OCCUPIED_TRIAL_LESSON_STATUSES,
            start_at__lt=check_end,
            end_at__gt=check_start,
        ).exists()

        if student_overlap:
            raise serializers.ValidationError({
                'start_at': 'You already have a trial lesson that conflicts with this time.'
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