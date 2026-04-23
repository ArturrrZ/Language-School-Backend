from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import TrialLessonRequest
# from .tasks import test_print_message

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

@receiver(post_save, sender=TrialLessonRequest)
def trial_lesson_request_post_save(sender, instance, created, **kwargs):
    """
    Signal to perform actions after a TrialLessonRequest is saved.
    """
    
    print(instance.status)
    if created:
        pass
        # Add your logic here for when a new trial lesson request is created
        # print(f'New TrialLessonRequest created with ID: {instance.id}')
    else:
        # Add your logic here for when a trial lesson request is updated
        # print(f'TrialLessonRequest with ID: {instance.id} has been updated')
        # print(f'Current status: {instance.status}')
        # test_print_message.delay(instance.id, instance.status)
        if instance.status == TrialLessonRequest.Status.TEACHER_CONFIRMED or instance.status == TrialLessonRequest.Status.ADMIN_APPROVED:
            print(f'TrialLessonRequest with ID: {instance.id} has been confirmed.')
            #send email to student about confirmation
        elif instance.status == TrialLessonRequest.Status.REJECTED:
            print(f'TrialLessonRequest with ID: {instance.id} has been rejected.')
            #send email to student about rejection
