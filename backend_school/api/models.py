from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
	phone = models.CharField(max_length=20, blank=True)
	is_student = models.BooleanField(default=False)
	is_teacher = models.BooleanField(default=False)
	is_parent = models.BooleanField(default=False)
	profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

	def save(self, *args, **kwargs):
		# old behavior: if self.is_teacher and not hasattr(self, 'teacher_profile'):
		#	Teacher.objects.create(user=self, teaching_experience=0, description='DONT DO THIS. ODD BEHAVIOR')
		super().save(*args, **kwargs)

	def clean(self):
		super().clean()
		
		if self.is_teacher:
			has_teacher_profile = bool(self.pk) and Teacher.objects.filter(user_id=self.pk).exists()
			if not has_teacher_profile:
				raise ValidationError({
					'is_teacher': 'You cannot set is_teacher=True without a Teacher profile. Create the Teacher profile first.',
				})

	def __str__(self) -> str:
		return self.get_full_name() or self.username

class Teacher(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
	teaching_experience = models.PositiveIntegerField(default=0)  # in years
	description = models.TextField()
	kids_description = models.TextField()

	def _invalidate_teacher_list_cache(self):
		cache_key = getattr(settings, 'TEACHER_LIST_CACHE_KEY', 'teachers:list:v1')
		cache.delete(cache_key)

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		self._invalidate_teacher_list_cache()

	def delete(self, *args, **kwargs):
		super().delete(*args, **kwargs)
		self._invalidate_teacher_list_cache()

	def __str__(self) -> str:
		return f"Teacher: {self.user.get_full_name() or self.user.username}"