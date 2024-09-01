from rest_framework import permissions, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from api.models import Task, UserProfile


class IsProfileOwnerOrReadOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        # Для небезопасных методов проверяем, что пользователь аутентифицирован и связан с профилем задачи
        task_id = view.kwargs.get('taskId')
        if not task_id:
            return NotFound("Task ID not provided")

        task = Task.objects.filter(id=task_id).first()
        if not task:
            return NotFound("Task not found")

        profile_ids = task.profile_set.values_list('id', flat=True)
        return request.user.is_authenticated and request.user.profile_set.filter(id__in=profile_ids).exists()


class TaskNotDonePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.status == 'DONE':
            raise PermissionDenied("This task is already completed and cannot be accessed.")
        return True


class SubmissionTaskNotDonePermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.task_id.status == 'DONE':
            raise PermissionDenied(
                "The task associated with this submission is already completed and cannot be accessed.")
        return True


class ProfileNotAddedToUserPermission(permissions.BasePermission):
    message = "The profile has already been added to the user"

    def has_permission(self, request, view):
        user = request.user
        profile = view.get_object()  # Assuming the view has a get_object method to retrieve the profile

        if UserProfile.objects.filter(user=user, profile=profile).exists():
            raise APIException(detail=self.message, code=status.HTTP_409_CONFLICT)
        return True
