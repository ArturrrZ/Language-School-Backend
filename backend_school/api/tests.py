from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Teacher, TeacherAvailability, TrialLessonRequest
from .services import create_trial_lesson_request


User = get_user_model()


class TrialLessonServiceTests(TestCase):
	def setUp(self):
		self.student = User.objects.create_user(username='student', password='pass', is_student=True)
		self.teacher_user = User.objects.create_user(username='teacher', password='pass', is_teacher=True)
		self.teacher = Teacher.objects.create(user=self.teacher_user, teaching_experience=1, description='x', kids_description='y')

	def test_prevents_teacher_overlap(self):
		start = timezone.now() + timedelta(days=1)
		end = start + timedelta(minutes=45)
		# create first
		r1 = create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start, end_at=end)
		self.assertEqual(r1.status, TrialLessonRequest.Status.PENDING)

		# attempt overlapping
		with self.assertRaises(Exception):
			create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start + timedelta(minutes=15), end_at=end + timedelta(minutes=15))

	def test_prevents_past_booking(self):
		start = timezone.now() - timedelta(days=1)
		end = start + timedelta(minutes=45)
		with self.assertRaises(Exception):
			create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start, end_at=end)

	def test_prevents_student_overlap(self):
		start = timezone.now() + timedelta(days=2)
		end = start + timedelta(minutes=45)
		# create first for this student
		r1 = create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start, end_at=end)
		self.assertEqual(r1.status, TrialLessonRequest.Status.PENDING)

		# attempt overlapping booking for same student with a different teacher
		other_teacher_user = User.objects.create_user(username='teacher2', password='pass', is_teacher=True)
		other_teacher = Teacher.objects.create(user=other_teacher_user, teaching_experience=2, description='x', kids_description='y')

		with self.assertRaises(Exception):
			create_trial_lesson_request(student=self.student, teacher=other_teacher, start_at=start + timedelta(minutes=10), end_at=end + timedelta(minutes=10))

	def test_respects_buffer_minutes(self):
		# ensure buffer around existing booking prevents nearby bookings
		from django.conf import settings
		buffer_minutes = getattr(settings, 'TRIAL_LESSON_BUFFER_MINUTES', 15)
		start = timezone.now() + timedelta(days=3)
		end = start + timedelta(minutes=45)
		r1 = create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start, end_at=end)
		self.assertEqual(r1.status, TrialLessonRequest.Status.PENDING)

		# attempt to book a slot that starts within the buffer after the first booking end
		start2 = end + timedelta(minutes=buffer_minutes - 5)
		end2 = start2 + timedelta(minutes=45)
		with self.assertRaises(Exception):
			create_trial_lesson_request(student=self.student, teacher=self.teacher, start_at=start2, end_at=end2)


class ConcurrencyTests(TransactionTestCase):
	reset_sequences = True

	def setUp(self):
		self.student1 = User.objects.create_user(username='student1', password='pass', is_student=True)
		self.student2 = User.objects.create_user(username='student2', password='pass', is_student=True)
		self.teacher_user = User.objects.create_user(username='teacherc', password='pass', is_teacher=True)
		self.teacher = Teacher.objects.create(user=self.teacher_user, teaching_experience=1, description='x', kids_description='y')

	def test_concurrent_creates_one_wins(self):
		"""Spawn two concurrent create attempts for overlapping slots; only one should succeed."""
		start = timezone.now() + timedelta(days=5)
		end = start + timedelta(minutes=45)

		results = []

		def attempt_create(student):
			try:
				tr = create_trial_lesson_request(student=student, teacher=self.teacher, start_at=start, end_at=end)
				results.append(('ok', tr.id))
			except Exception as e:
				results.append(('err', str(e)))

		import threading

		t1 = threading.Thread(target=attempt_create, args=(self.student1,))
		t2 = threading.Thread(target=attempt_create, args=(self.student2,))

		t1.start()
		t2.start()
		t1.join()
		t2.join()

		# At most one should succeed; at least one should fail.
		oks = [r for r in results if r[0] == 'ok']
		errs = [r for r in results if r[0] == 'err']
		self.assertLessEqual(len(oks), 1, msg=f'Expected at most 1 success, got {len(oks)}; results: {results}')
		self.assertGreaterEqual(len(errs), 1, msg=f'Expected at least 1 failure, got {len(errs)}; results: {results}')


class TrialLessonFlowIntegrationTests(APITestCase):
	def setUp(self):
		self.student = User.objects.create_user(username='flow_student', password='pass', is_student=True)
		self.other_student = User.objects.create_user(username='flow_other_student', password='pass', is_student=True)
		self.teacher_user = User.objects.create_user(username='flow_teacher', password='pass', is_teacher=True)
		self.teacher = Teacher.objects.create(
			user=self.teacher_user,
			teaching_experience=4,
			description='Teacher description',
			kids_description='Kids description',
		)

	def test_create_then_cancel_then_list_shows_cancelled(self):
		self.client.force_authenticate(user=self.student)

		start = timezone.now() + timedelta(days=6)
		end = start + timedelta(minutes=45)
		create_payload = {
			'teacher': self.teacher.id,
			'start_at': start.isoformat(),
			'end_at': end.isoformat(),
			'student_note': 'Looking forward to the lesson',
		}

		create_response = self.client.post(
			reverse('trial_lesson_create'),
			create_payload,
			format='json',
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(create_response.data['status'], TrialLessonRequest.Status.PENDING)

		trial_request_id = create_response.data['id']
		cancel_response = self.client.post(reverse('student_trial_lesson_cancel', kwargs={'trial_request_id': trial_request_id}))
		self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
		self.assertEqual(cancel_response.data['id'], trial_request_id)
		self.assertEqual(cancel_response.data['status'], TrialLessonRequest.Status.CANCELLED)

		list_response = self.client.get(reverse('my_trial_lessons'))
		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(list_response.data), 1)
		self.assertEqual(list_response.data[0]['id'], trial_request_id)
		self.assertEqual(list_response.data[0]['status'], TrialLessonRequest.Status.CANCELLED)

	def test_only_owner_can_cancel_and_cannot_cancel_twice(self):
		start = timezone.now() + timedelta(days=7)
		end = start + timedelta(minutes=45)
		trial_request = TrialLessonRequest.objects.create(
			student=self.student,
			teacher=self.teacher,
			start_at=start,
			end_at=end,
			status=TrialLessonRequest.Status.PENDING,
		)

		self.client.force_authenticate(user=self.other_student)
		not_owner_cancel = self.client.post(
			reverse('student_trial_lesson_cancel', kwargs={'trial_request_id': trial_request.id})
		)
		self.assertEqual(not_owner_cancel.status_code, status.HTTP_404_NOT_FOUND)

		self.client.force_authenticate(user=self.student)
		first_cancel = self.client.post(reverse('student_trial_lesson_cancel', kwargs={'trial_request_id': trial_request.id}))
		self.assertEqual(first_cancel.status_code, status.HTTP_200_OK)
		self.assertEqual(first_cancel.data['status'], TrialLessonRequest.Status.CANCELLED)

		second_cancel = self.client.post(reverse('student_trial_lesson_cancel', kwargs={'trial_request_id': trial_request.id}))
		self.assertEqual(second_cancel.status_code, status.HTTP_404_NOT_FOUND)


class ApiUrlsCoverageTests(APITestCase):
	def setUp(self):
		self.student = User.objects.create_user(
			username='url_student',
			email='url_student@example.com',
			password='pass',
			is_student=True,
		)
		self.teacher_user = User.objects.create_user(
			username='url_teacher',
			email='url_teacher@example.com',
			password='pass',
			is_teacher=True,
		)
		self.other_user = User.objects.create_user(
			username='url_other',
			email='url_other@example.com',
			password='pass',
		)
		self.teacher = Teacher.objects.create(
			user=self.teacher_user,
			teaching_experience=5,
			description='Senior teacher',
			kids_description='Great with kids',
		)
		TeacherAvailability.objects.create(
			teacher=self.teacher,
			weekday=0,
			start_time=time(9, 0),
			end_time=time(11, 0),
			is_active=True,
		)

		self.trial = TrialLessonRequest.objects.create(
			student=self.student,
			teacher=self.teacher,
			start_at=timezone.now() + timedelta(days=2),
			end_at=timezone.now() + timedelta(days=2, minutes=45),
			status=TrialLessonRequest.Status.PENDING,
		)

	def test_auth_register_login_logout_me(self):
		me_anon = self.client.get(reverse('me'))
		self.assertEqual(me_anon.status_code, status.HTTP_200_OK)
		self.assertEqual(me_anon.data.get('auth'), False)

		register_response = self.client.post(
			reverse('register'),
			{'username': 'new_user', 'email': 'new_user@example.com', 'password': 'pass12345'},
			format='json',
		)
		self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

		login_response = self.client.post(
			reverse('login'),
			{'username': 'url_student', 'password': 'pass'},
			format='json',
		)
		self.assertEqual(login_response.status_code, status.HTTP_200_OK)

		me_auth = self.client.get(reverse('me'))
		self.assertEqual(me_auth.status_code, status.HTTP_200_OK)
		self.assertEqual(me_auth.data.get('auth'), True)

		logout_response = self.client.post(reverse('logout'))
		self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

	def test_teachers_and_availability_urls(self):
		teachers_response = self.client.get(reverse('teacher_list'))
		self.assertEqual(teachers_response.status_code, status.HTTP_200_OK)
		self.assertGreaterEqual(len(teachers_response.data), 1)

		availability_windows = self.client.get(
			reverse('teacher_availability', kwargs={'teacher_id': self.teacher.id})
		)
		self.assertEqual(availability_windows.status_code, status.HTTP_200_OK)

		availability_invalid_date = self.client.get(
			reverse('teacher_availability', kwargs={'teacher_id': self.teacher.id}),
			{'date': '2026-99-99'},
		)
		self.assertEqual(availability_invalid_date.status_code, status.HTTP_400_BAD_REQUEST)

		availability_date = self.client.get(
			reverse('teacher_availability', kwargs={'teacher_id': self.teacher.id}),
			{'date': '2030-01-07'},
		)
		self.assertEqual(availability_date.status_code, status.HTTP_200_OK)
		self.assertIn('slots', availability_date.data)

	def test_trial_lesson_create_my_and_cancel_urls(self):
		unauth_create = self.client.post(reverse('trial_lesson_create'), {}, format='json')
		self.assertEqual(unauth_create.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(user=self.student)
		start = timezone.now() + timedelta(days=10)
		end = start + timedelta(minutes=45)
		create_response = self.client.post(
			reverse('trial_lesson_create'),
			{
				'teacher': self.teacher.id,
				'start_at': start.isoformat(),
				'end_at': end.isoformat(),
				'student_note': 'Please schedule',
			},
			format='json',
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		my_list = self.client.get(reverse('my_trial_lessons'))
		self.assertEqual(my_list.status_code, status.HTTP_200_OK)

		cancel_response = self.client.post(
			reverse('student_trial_lesson_cancel', kwargs={'trial_request_id': self.trial.id})
		)
		self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
		self.assertEqual(cancel_response.data['status'], TrialLessonRequest.Status.CANCELLED)

	def test_teacher_trial_urls(self):
		self.client.force_authenticate(user=self.other_user)
		not_teacher_list = self.client.get(reverse('teacher_trial_lessons'))
		self.assertEqual(not_teacher_list.status_code, status.HTTP_404_NOT_FOUND)

		self.client.force_authenticate(user=self.teacher_user)
		teacher_list = self.client.get(reverse('teacher_trial_lessons'))
		self.assertEqual(teacher_list.status_code, status.HTTP_200_OK)

		update_response = self.client.put(
			reverse('teacher_trial_lesson_update', kwargs={'trial_request_id': self.trial.id}),
			{'status': TrialLessonRequest.Status.TEACHER_CONFIRMED, 'teacher_note': 'See you soon'},
			format='json',
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data['status'], TrialLessonRequest.Status.TEACHER_CONFIRMED)

	def test_free_consultation_url(self):
		response = self.client.post(
			reverse('free_consultation_create'),
			{
				'name': 'Jane Parent',
				'email': 'jane.parent@example.com',
				'phone': '+1234567890',
				'message': 'Please contact me about classes.',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data.get('detail'), 'Free consultation request submitted successfully.')
