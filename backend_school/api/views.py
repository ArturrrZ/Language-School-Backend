from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .services import create_trial_lesson_request
from .models import Teacher, TeacherAvailability, TrialLessonRequest
from .tasks import send_free_consultation_admin_email
from django.views.decorators.csrf import csrf_exempt
from .serializers import (
    AvailableSlotSerializer,
    FreeConsultationRequestSerializer,
    MeSerializer,
    TeacherAvailabilitySerializer,
    TeacherSerializer,
    TrialLessonRequestCreateSerializer,
    TrialLessonRequestSerializer,
)

User = get_user_model()


OCCUPIED_TRIAL_LESSON_STATUSES = (
    TrialLessonRequest.Status.PENDING,
    TrialLessonRequest.Status.TEACHER_CONFIRMED,
    TrialLessonRequest.Status.ADMIN_APPROVED,
)


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and a_end > b_start


def _get_available_slots(teacher, target_date, slot_minutes=45, buffer_minutes=15):
    # print(f"Calculating available slots for Teacher {teacher.id} on {target_date} with slot_minutes={slot_minutes} and buffer_minutes={buffer_minutes}")
    weekday = target_date.weekday()
    windows = teacher.availabilities.filter(weekday=weekday, is_active=True).order_by('start_time')
    # print(f"Found {windows.count()} availability windows for weekday {weekday}:")
    current_timezone = timezone.get_current_timezone()
    # print(f"Current timezone: {current_timezone}")
    day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()), current_timezone)
    day_end = day_start + timedelta(days=1)

    bookings = list(teacher.trial_lesson_requests.filter(
        status__in=OCCUPIED_TRIAL_LESSON_STATUSES,
        start_at__lt=day_end,
        end_at__gt=day_start,
    ).values('start_at', 'end_at'))
    # print(bookings)
    available_slots = []
    slot_delta = timedelta(minutes=slot_minutes)
    buffer_delta = timedelta(minutes=buffer_minutes)
    now = timezone.now()
    # now = datetime.time.

    for window in windows:
        current = timezone.make_aware(datetime.combine(target_date, window.start_time), current_timezone)
        window_end = timezone.make_aware(datetime.combine(target_date, window.end_time), current_timezone)

        while current + slot_delta <= window_end:
            slot_start = current
            slot_end = current + slot_delta

            is_busy = False
            for booking in bookings:
                booking_start = booking['start_at'] - buffer_delta
                booking_end = booking['end_at'] + buffer_delta
                if _overlaps(slot_start, slot_end, booking_start, booking_end):
                    is_busy = True
                    break

            if not is_busy and slot_start > now:
                available_slots.append({
                    'start_at': slot_start,
                    'end_at': slot_end,
                })

            current = current + slot_delta + buffer_delta

    return available_slots
#
class TeacherListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = getattr(settings, 'TEACHER_LIST_CACHE_KEY', 'teachers:list:v1')
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        print("DB QUERY: Fetching teachers from database")
        teachers = Teacher.objects.select_related('user').all()
        serializer = TeacherSerializer(teachers, many=True, context={'request': request})
        data = serializer.data
        cache.set(
            cache_key,
            data,
            timeout=getattr(settings, 'TEACHER_LIST_CACHE_TTL_SECONDS', 7*24*60*60),
        )
        return Response(data)


class TeacherAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, teacher_id: int):
        try:
            teacher = Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            return Response({'detail': 'Teacher not found.'}, status=status.HTTP_404_NOT_FOUND)

        requested_date = request.query_params.get('date')
        if not requested_date:
            availability = TeacherAvailability.objects.filter(
                teacher_id=teacher_id,
                is_active=True,
            ).order_by('weekday', 'start_time')
            serializer = TeacherAvailabilitySerializer(availability, many=True)
            return Response(serializer.data)

        try:
            target_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'detail': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots = _get_available_slots(
            teacher=teacher,
            target_date=target_date,
            slot_minutes=getattr(settings, 'TRIAL_LESSON_SLOT_MINUTES', 45),
            buffer_minutes=getattr(settings, 'TRIAL_LESSON_BUFFER_MINUTES', 15),
        )
        serializer = AvailableSlotSerializer(slots, many=True)
        return Response(
            {
                'teacher_id': teacher.id,
                'date': target_date.isoformat(),
                'slot_minutes': getattr(settings, 'TRIAL_LESSON_SLOT_MINUTES', 45),
                'buffer_minutes': getattr(settings, 'TRIAL_LESSON_BUFFER_MINUTES', 15),
                'slots': serializer.data,
            }
        )


class TrialLessonRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        existing_trial_lesson_same_date = TrialLessonRequest.objects.filter(
            student=request.user,
            start_at__date=request.data.get('start_at', '')[:10],  # crude way to extract date
            status__in=OCCUPIED_TRIAL_LESSON_STATUSES,
        ).exists()
        if existing_trial_lesson_same_date:
            return Response(
                {'detail': 'You already have a trial lesson request on this date.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TrialLessonRequestCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # trial_request = serializer.save()
        trial_request = create_trial_lesson_request(
            student=request.user,
            teacher=serializer.validated_data['teacher'],
            start_at=serializer.validated_data['start_at'],
            end_at=serializer.validated_data['end_at'],
            student_note=serializer.validated_data.get('student_note', ''),
        )
        return Response(
            TrialLessonRequestSerializer(trial_request).data,
            status=status.HTTP_201_CREATED,
        )


class MyTrialLessonRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = TrialLessonRequest.objects.select_related('teacher__user', 'student').filter(
            student=request.user
        )
        serializer = TrialLessonRequestSerializer(queryset, many=True)
        return Response(serializer.data)



#-----------------------------Teacher----------------------------------------------

class TeacherTrialLessonRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        teacher = Teacher.objects.filter(user=request.user).first()
        if not teacher:
            return Response({'detail': 'Teacher profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        queryset = TrialLessonRequest.objects.select_related('teacher__user', 'student').filter(
            teacher=teacher, status=TrialLessonRequest.Status.PENDING
        )
        serializer = TrialLessonRequestSerializer(queryset, many=True)
        return Response(serializer.data)

class TeacherTrialLessonRequestUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, trial_request_id: int):
        teacher = Teacher.objects.filter(user=request.user).first()
        if not teacher:
            return Response({'detail': 'Teacher profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        trial_request = TrialLessonRequest.objects.filter(
            id=trial_request_id,
            teacher=teacher,
            status__in=[
                TrialLessonRequest.Status.PENDING,
                TrialLessonRequest.Status.TEACHER_CONFIRMED,
                TrialLessonRequest.Status.ADMIN_APPROVED,
                TrialLessonRequest.Status.REJECTED,
            ],
        ).first()
        if not trial_request:
            return Response({'detail': 'Trial lesson request not found or cannot be updated.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status not in dict(TrialLessonRequest.Status.choices):
            return Response({'detail': 'Invalid status value.'}, status=status.HTTP_400_BAD_REQUEST)

        trial_request.status = new_status
        teacher_note = request.data.get('teacher_note', '')
        if teacher_note:
            trial_request.teacher_note = teacher_note       
        trial_request.save()
        return Response(TrialLessonRequestSerializer(trial_request).data)

#-----------------------------AUTH----------------------------------------------

class MeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        get_token(request)
        if not request.user.is_authenticated:
            return Response({"auth": False})
        serializer = MeSerializer(request.user, context={'request': request})
        return Response({"auth": True, **serializer.data})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {"detail": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email=email).exists():
            return Response(
                {"detail": "Email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.create_user(username=username, email=email, password=password)
        auth_login(request, user)
        response = Response({"detail": "Registered."}, status=status.HTTP_201_CREATED)
        get_token(request)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        auth_login(request, user)
        print(f"User {user.username} logged in. Session created.")
        response = Response({"detail": "Logged in."}, status=status.HTTP_200_OK)
        get_token(request)
        return response

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_logout(request)
        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        return response

#-----------------------------Free Consultation----------------------------------------------

class FreeConsultationRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FreeConsultationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consultation_request = serializer.save()
        send_free_consultation_admin_email.delay(consultation_request.id)

        return Response(
            {
                'detail': 'Free consultation request submitted successfully.',
                'request': FreeConsultationRequestSerializer(consultation_request).data,
            },
            status=status.HTTP_201_CREATED,
        )
    