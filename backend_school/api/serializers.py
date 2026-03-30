from django.utils import timezone
from rest_framework import serializers

from .models import Teacher, TeacherAvailability, TrialLessonRequest


class TeacherSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = (
            'id',
            'name',
            'teaching_experience',
            'description',
            'kids_description',
            'profile_picture',
        )

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        picture = obj.user.profile_picture
        if not picture:
            return None
        if request:
            return request.build_absolute_uri(picture.url)
        return picture.url


class TeacherAvailabilitySerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = TeacherAvailability
        fields = ('id', 'weekday', 'weekday_label', 'start_time', 'end_time', 'is_active')


class AvailableSlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()


class TrialLessonRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrialLessonRequest
        fields = ('id', 'teacher', 'start_at', 'end_at', 'student_note')
        read_only_fields = ('id',)

    def validate(self, attrs):
        start_at = attrs['start_at']
        end_at = attrs['end_at']
        teacher = attrs['teacher']

        if start_at >= end_at:
            raise serializers.ValidationError({'end_at': 'End datetime must be after start datetime.'})

        if start_at <= timezone.now():
            raise serializers.ValidationError({'start_at': 'Trial lesson must be in the future.'})

        overlap_exists = TrialLessonRequest.objects.filter(
            teacher=teacher,
            status__in=(
                TrialLessonRequest.Status.PENDING,
                TrialLessonRequest.Status.TEACHER_CONFIRMED,
                TrialLessonRequest.Status.ADMIN_APPROVED,
            ),
            start_at__lt=end_at,
            end_at__gt=start_at,
        ).exists()
        if overlap_exists:
            raise serializers.ValidationError({'start_at': 'Teacher already has a lesson in this time range.'})

        return attrs

    def create(self, validated_data):
        request = self.context['request']
        return TrialLessonRequest.objects.create(student=request.user, **validated_data)


class TrialLessonRequestSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = TrialLessonRequest
        fields = (
            'id',
            'teacher',
            'teacher_name',
            'student',
            'student_name',
            'start_at',
            'end_at',
            'status',
            'student_note',
            'admin_note',
            'zoom_join_url_student',
            'zoom_join_url_teacher',
            'created_at',
            'updated_at',
        )

    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name() or obj.teacher.user.username

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username


class TrialLessonDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            TrialLessonRequest.Status.TEACHER_CONFIRMED,
            TrialLessonRequest.Status.ADMIN_APPROVED,
            TrialLessonRequest.Status.REJECTED,
            TrialLessonRequest.Status.CANCELLED,
        )
    )
    admin_note = serializers.CharField(required=False, allow_blank=True)
