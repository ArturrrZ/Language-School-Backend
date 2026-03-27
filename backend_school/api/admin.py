from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Teacher, User


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
