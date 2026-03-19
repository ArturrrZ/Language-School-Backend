from django.contrib import admin
from .models import User, Teacher
# Register your models here.

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_student', 'is_teacher', 'is_parent', )
    list_filter = ('is_student', 'is_teacher', 'is_parent')
    exclude = ('password',)  # Exclude password from admin form for security reasons
    
admin.site.register(User, UserAdmin)
admin.site.register(Teacher)
