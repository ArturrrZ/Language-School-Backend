from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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


class TeacherAvailability(models.Model):
	class Weekday(models.IntegerChoices):
		MONDAY = 0, 'Monday'
		TUESDAY = 1, 'Tuesday'
		WEDNESDAY = 2, 'Wednesday'
		THURSDAY = 3, 'Thursday'
		FRIDAY = 4, 'Friday'
		SATURDAY = 5, 'Saturday'
		SUNDAY = 6, 'Sunday'

	teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='availabilities')
	weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
	start_time = models.TimeField(help_text='Start time of availability window in Pacific Time')
	end_time = models.TimeField(help_text='End time of availability window in Pacific Time')
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ('teacher', 'weekday', 'start_time')
		constraints = [
			models.UniqueConstraint(
				fields=['teacher', 'weekday', 'start_time', 'end_time'],
				name='uniq_teacher_weekday_time_range',
			),
		]

	def clean(self):
		super().clean()
		if self.start_time >= self.end_time:
			raise ValidationError({'end_time': 'End time must be after start time.'})

	def __str__(self) -> str:
		return f'{self.teacher} | {self.get_weekday_display()} {self.start_time}-{self.end_time}'


class TrialLessonRequest(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		TEACHER_CONFIRMED = 'teacher_confirmed', 'Teacher confirmed'
		ADMIN_APPROVED = 'admin_approved', 'Admin approved'
		REJECTED = 'rejected', 'Rejected'
		CANCELLED = 'cancelled', 'Cancelled'

	student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trial_lesson_requests')
	teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='trial_lesson_requests')
	start_at = models.DateTimeField()
	end_at = models.DateTimeField()
	status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
	student_note = models.TextField(blank=True)
	teacher_note = models.TextField(blank=True)
	admin_note = models.TextField(blank=True)
	zoom_join_url_student = models.URLField(blank=True)
	zoom_join_url_teacher = models.URLField(blank=True)
	zoom_start_url_host = models.URLField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ('-created_at',)
		indexes = [
			models.Index(fields=['teacher', 'start_at']),
			models.Index(fields=['student', 'status']),
		]

	def clean(self):
		super().clean()
		if self.start_at >= self.end_at:
			raise ValidationError({'end_at': 'End datetime must be after start datetime.'})
		if self.start_at <= timezone.now():
			raise ValidationError({'start_at': 'Trial lesson must be in the future.'})
		if self.status == self.Status.REJECTED and not self.admin_note:
			raise ValidationError({'admin_note': 'Admin note is required when rejecting a trial lesson request.'})

	def __str__(self) -> str:
		return f'TrialRequest #{self.pk} | {self.student} -> {self.teacher} ({self.status})'
	

class Notification(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
	type = models.CharField(max_length=50, blank=True, null=True)
	message = models.TextField()
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ('-created_at',)

	def __str__(self) -> str:
		return f'Notification for {self.user} at {self.created_at}'


class FreeConsultationRequest(models.Model):
	name = models.CharField(max_length=255)
	email = models.EmailField()
	message = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	phone = models.CharField(max_length=20, blank=True)

	class Meta:
		ordering = ('-created_at',)

	def __str__(self) -> str:
		return f'Free consultation request #{self.pk} from {self.name} <{self.email}>'