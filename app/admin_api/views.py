from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView, get_object_or_404
from rest_framework.mixins import CreateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


from api.filters import SubmissionsFilter
from users.models import UserActionLog
from users.serializers import UserSerializer, UserChangePasswordSerializer
from api.serializers import ProfileSerializer, TaskSerializer, SubmissionSerializer, GroupedSubmissionSerializer, \
    ProfileChangeSerializer, SubmissionAdminUpdateSerializer
from .permissions import IsAdmin
from api.models import Profile, Task, Submission, UserProfile
from .filters import ProfilesFilter, UsersFilter, UserLogsFilter
from .serializers import UserActionLogSerializer
from rest_framework.viewsets import ViewSet
from api.views import BaseListLangAPIView

User = get_user_model()


class AdminBaseListView(BaseListLangAPIView):
    list_base_cache_name: str = None
    permission_classes = (IsAdmin,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = None
    ordering_fields = ()

    def get(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response


class AdminUsersListView(AdminBaseListView):
    list_base_cache_name = 'admin_users'
    filterset_class = UsersFilter
    ordering_fields = ('username', 'email')
    ordering = ('id',)

    def get_queryset(self):
        return User.objects.prefetch_related('profiles')

    def get_serializer(self, *args, **kwargs):
        kwargs['exclude_fields'] = ('profiles',)
        return UserSerializer(*args, **kwargs)


class AdminUserViewSet(ViewSet):
    permission_classes = (IsAdmin,)

    @action(["post"], detail=False)
    def set_profile(self, request, *args, **kwargs):
        serializer = ProfileChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        profile = serializer.validated_data['profile']

        user_profile, created = UserProfile.objects.get_or_create(user=user, profile=profile)
        if not created:
            return Response({"detail": "The profile has already been added to the user"}, status=status.HTTP_409_CONFLICT)

        return Response({"detail": "Profile added successfully"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def set_password(self, request, *args, **kwargs):
        serializer = UserChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(User, id=serializer.validated_data["user_id"])
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        try:
            self.logout_user(user)  # Реализация функции logout_user
            return Response({"detail": "Password changed successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except (ObjectDoesNotExist, TokenError) as err:
            return Response({'message': str(err)}, status=status.HTTP_400_BAD_REQUEST)

    def logout_user(self, user):
        try:
            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
        except (ObjectDoesNotExist, TokenError):
            pass


class AdminProfileListCreateView(CreateModelMixin, AdminBaseListView):
    list_base_cache_name = 'admin_profiles'
    filterset_class = ProfilesFilter
    ordering = ('id',)

    def get_serializer(self, *args, **kwargs):
        method = self.request.method
        if method == 'GET':
            lang = self.get_exclude_lang()
            kwargs['exclude_fields'] = ('tasks', 'files', f'description_{lang}', f'description_{lang}_html')
            return ProfileSerializer(*args, **kwargs)
        else:
            return ProfileSerializer(*args, **kwargs)

    def get_queryset(self):
        return Profile.objects.prefetch_related('tasks')

    def get_ordering_fields(self):
        fields = ('id', f'tasks_count')
        return fields

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class AdminRetrieveUpdateDestroyProfileView(RetrieveUpdateDestroyAPIView):
    lookup_url_kwarg = "profileId"
    permission_classes = (IsAdmin,)
    serializer_class = ProfileSerializer

    def get_queryset(self):
        return Profile.objects.prefetch_related('tasks')


class AdminTaskListCreateView(CreateModelMixin, AdminBaseListView):
    list_base_cache_name = 'admin_tasks'
    ordering = ('id',)

    def get_queryset(self):
        return Task.objects.select_related('profile_id').prefetch_related('submissions')

    def get_serializer(self, *args, **kwargs):
        method = self.request.method
        if method == 'GET':
            lang = self.get_exclude_lang()
            kwargs['exclude_fields'] = (
                f'title_{lang}', f'description_{lang}', f'description_{lang}_html', 'profile_id', 'profile')
            return TaskSerializer(*args, **kwargs)
        else:
            return TaskSerializer(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.context['profileId'] = request.data.get('profile_id')

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        profile_id = serializer.context.get('profileId')
        profile = Profile.objects.get(id=profile_id)
        serializer.save(
            profile_id=profile
        )

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def get_ordering_fields(self):
        fields = ('id', 'status', 'type', 'submissions_count', f'title_{self.lang}')
        return fields


class AdminRetrieveUpdateDestroyTaskView(RetrieveUpdateDestroyAPIView):
    lookup_url_kwarg = "taskId"
    permission_classes = (IsAdmin,)
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.select_related('profile_id').prefetch_related('submissions')


class AdminSubmissionsListView(ListAPIView):
    permission_classes = (IsAdmin,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = SubmissionsFilter
    ordering_fields = ('status',)

    def get_queryset(self):
        return Submission.objects.select_related('task_id').only("id", "status", "user_id", "task_id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        grouped_submissions = {}
        for submission in queryset:
            task_id = submission.task_id.id
            if task_id not in grouped_submissions:
                grouped_submissions[task_id] = {
                    'task_id': task_id,
                    'submissions': []
                }
            grouped_submissions[task_id]['submissions'].append(submission)

        grouped_submissions_list = list(grouped_submissions.values())

        page = self.paginate_queryset(grouped_submissions_list)
        if page is not None:
            serializer = GroupedSubmissionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = GroupedSubmissionSerializer(grouped_submissions_list, many=True)
        return Response(serializer.data)


class AdminRetrieveUpdateDestroySubmissionView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAdmin,)
    serializer_class = SubmissionSerializer

    def get_serializer(self, *args, **kwargs):
        method = self.request.method
        if method == 'PUT':
            return SubmissionAdminUpdateSerializer(*args, **kwargs)
        else:
            return SubmissionSerializer(*args, **kwargs)

    def get_object(self):
        submission_id = self.kwargs.get('submissionId')
        obj = get_object_or_404(Submission.objects.prefetch_related('change_history'), id=submission_id)
        self.check_object_permissions(self.request, obj)
        return obj


class AdminUserActionLogListView(ListAPIView):
    queryset = UserActionLog.objects.select_related('user').all()
    serializer_class = UserActionLogSerializer
    permission_classes = (IsAdmin,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = UserLogsFilter
    ordering_fields = ('id', 'timestamp')
    ordering = ('timestamp',)
