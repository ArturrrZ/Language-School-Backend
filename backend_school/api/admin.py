from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Teacher, TeacherAvailability, TrialLessonRequest, User, Notification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_student', 'is_teacher', 'is_parent', 'is_staff')
    list_filter = ('is_student', 'is_teacher', 'is_parent', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')

    readonly_fields = ('last_login', 'date_joined','is_teacher')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role and profile', {'fields': ('phone', 'profile_picture', 'is_student', 'is_teacher', 'is_parent')}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role and profile', {'fields': ('email', 'phone', 'is_student', 'is_teacher', 'is_parent')}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'teaching_experience',)
    search_fields = ['user__username', 'user__email']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and not obj.user.is_teacher:
            obj.user.is_teacher = True
            obj.user.save(update_fields=['is_teacher'])
    def delete_model(self, request, obj):
        user = obj.user
        super().delete_model(request, obj)
        if user.is_teacher:
            user.is_teacher = False
            user.save()


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'weekday', 'start_time', 'end_time', 'is_active')
    list_filter = ('weekday', 'is_active')
    search_fields = ('teacher__user__username', 'teacher__user__email')


@admin.register(TrialLessonRequest)
class TrialLessonRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'teacher', 'start_at', 'end_at', 'status', 'created_at')
    list_editable = ('status',)
    list_filter = ('status', 'start_at', 'created_at')
    search_fields = ('student__username', 'student__email', 'teacher__user__username', 'teacher__user__email')
    actions = ('mark_teacher_confirmed', 'mark_admin_approved', 'mark_rejected', 'mark_cancelled')

    @admin.action(description='Set status: teacher confirmed')
    def mark_teacher_confirmed(self, request, queryset):
        queryset.update(status=TrialLessonRequest.Status.TEACHER_CONFIRMED)

    @admin.action(description='Set status: admin approved')
    def mark_admin_approved(self, request, queryset):
        queryset.update(status=TrialLessonRequest.Status.ADMIN_APPROVED)

    @admin.action(description='Set status: rejected')
    def mark_rejected(self, request, queryset):
        queryset.update(status=TrialLessonRequest.Status.REJECTED)

    @admin.action(description='Set status: cancelled')
    def mark_cancelled(self, request, queryset):
        queryset.update(status=TrialLessonRequest.Status.CANCELLED)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'message', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__username', 'user__email', 'message')