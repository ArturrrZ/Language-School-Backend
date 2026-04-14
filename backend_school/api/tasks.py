from celery import shared_task
from .models import TrialLessonRequest

@shared_task
def test_print_message(*args, **kwargs):
    print("Hello from Celery!")
    for arg in args:
        print(f"Argument: {arg}")
    return "Message printed successfully."