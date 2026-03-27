from rest_framework import serializers

from .models import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = (
            'id',
            'name',
            'teaching_experience',
            'description',
            'kids_description',
        )

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
