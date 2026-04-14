from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Teacher, TrialLessonRequest

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to create a user profile when a new user is created.
    """
    if created:
        # Add your profile creation logic here
        pass


@receiver(post_delete, sender=User)
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
        # Add your logic here for when a new trial lesson request is created
        print(f'New TrialLessonRequest created with ID: {instance.id}')
    else:
        # Add your logic here for when a trial lesson request is updated
        print(f'TrialLessonRequest with ID: {instance.id} has been updated')
        print(f'Current status: {instance.status}')
