from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
	phone = models.CharField(max_length=20, blank=True)
	is_student = models.BooleanField(default=False)
	is_teacher = models.BooleanField(default=False)
	is_parent = models.BooleanField(default=False)
	profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

	def __str__(self) -> str:
		return self.get_full_name() or self.username

class Teacher(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
	teaching_experience = models.PositiveIntegerField(default=0)  # in years
	description = models.TextField()

	def __str__(self) -> str:
		return f"Teacher: {self.user.get_full_name() or self.user.username}"