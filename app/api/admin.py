from django.contrib import admin
from .models import User, Profile, Task, Submission, SubmissionHistory, UserProfile, TaskProfile, TaskSubmission, \
    ProfileFile


# Регистрация моделей
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username')


class TaskSubmissionInline(admin.TabularInline):
    model = TaskSubmission
    extra = 0


class ProfileSubmissionInline(admin.TabularInline):
    model = UserProfile
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    inlines = [ProfileSubmissionInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    inlines = [TaskSubmissionInline]


admin.site.register(Submission)
admin.site.register(SubmissionHistory)
admin.site.register(UserProfile)
admin.site.register(TaskProfile)
admin.site.register(TaskSubmission)
admin.site.register(ProfileFile)
