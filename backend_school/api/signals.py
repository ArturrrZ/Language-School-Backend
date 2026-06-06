from django.db.models.signals import post_save, post_delete, pre_save
from django.db import transaction
from django.dispatch import receiver
from django.conf import settings
from django.core.cache import cache
from .models import TrialLessonRequest, Notification, Teacher
from .tasks import send_trial_status_email


def _teacher_list_cache_key() -> str:
    return getattr(settings, 'TEACHER_LIST_CACHE_KEY', 'teachers:list:v1')


IGNORED_USER_UPDATE_FIELDS_FOR_TEACHER_LIST_CACHE = {'last_login'}


@receiver(post_save, sender=Teacher)
@receiver(post_delete, sender=Teacher)
def invalidate_teacher_list_cache_on_teacher_change(sender, instance, **kwargs):
    cache.delete(_teacher_list_cache_key())


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def invalidate_teacher_list_cache_on_user_save(sender, instance, created, **kwargs):
    if not hasattr(instance, 'teacher_profile'):
        return

    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        if set(update_fields).issubset(IGNORED_USER_UPDATE_FIELDS_FOR_TEACHER_LIST_CACHE):
            return

    cache.delete(_teacher_list_cache_key())


@receiver(post_delete, sender=settings.AUTH_USER_MODEL)
def invalidate_teacher_list_cache_on_user_delete(sender, instance, **kwargs):
    if hasattr(instance, 'teacher_profile'):
        cache.delete(_teacher_list_cache_key())

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to create a user profile when a new user is created.
    """
    if created:
        # Add your profile creation logic here
        pass


@receiver(post_delete, sender=settings.AUTH_USER_MODEL)
def delete_user_profile(sender, instance, **kwargs):
    """
    Signal to delete associated data when a user is deleted.
    """
    pass


@receiver(pre_save, sender=TrialLessonRequest)
def trial_lesson_request_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_status = None
        instance._old_admin_note = None
        instance._old_teacher_note = None
        return

    previous = TrialLessonRequest.objects.filter(pk=instance.pk).values('status', 'admin_note', 'teacher_note').first()
    instance._old_status = previous['status'] if previous else None
    instance._old_admin_note = previous['admin_note'] if previous else None
    instance._old_teacher_note = previous['teacher_note'] if previous else None

@receiver(post_save, sender=TrialLessonRequest)
def trial_lesson_request_post_save(sender, instance, created, **kwargs):
    """
    Signal to perform actions after a TrialLessonRequest is saved.
    """
    if created:
        return

    old_status = getattr(instance, '_old_status', None)
    old_admin_note = getattr(instance, '_old_admin_note', None)
    old_teacher_note = getattr(instance, '_old_teacher_note', None)
    new_status = instance.status

    status_changed = old_status != new_status
    admin_note_changed = old_admin_note != instance.admin_note
    teacher_note_changed = old_teacher_note != instance.teacher_note

    if not status_changed and not admin_note_changed and not teacher_note_changed:
        return

    if status_changed:
        status_label = instance.get_status_display()
        teacher_name = instance.teacher.user.get_full_name() or instance.teacher.user.username
        message = (
            f'Your trial lesson request #{instance.id} with {teacher_name} '
            f'has a new status: {status_label}.'
        )

        if new_status == TrialLessonRequest.Status.REJECTED and instance.admin_note:
            message = f'{message} Reason: {instance.admin_note}'

        Notification.objects.create(
            user=instance.student,
            type='trial_request_status',
            message=message,
        )

    transaction.on_commit(
        lambda: send_trial_status_email.delay(instance.id, old_status)
    )
    