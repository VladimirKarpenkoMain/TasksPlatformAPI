from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.mixins import CreateModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from django.core.cache import cache

from api.exceptions import DuplicateSubmissionError
from api.mixins import UserActionLogMixin
from api.models import Profile, Task, Submission
from api.filters import TasksFilter, SubmissionsFilter
from api.serializers import ProfileSerializer, TaskSerializer, SubmissionSerializer, SubmissionCreateUpdateSerializer
from api.permissions import IsProfileOwnerOrReadOnly, TaskNotDonePermission, SubmissionTaskNotDonePermission

User = get_user_model()


class BaseLangAPIView(UserActionLogMixin, GenericAPIView):

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.lang = self.kwargs.get('lang')

    def get_exclude_lang(self) -> str:
        if self.lang == "ru":
            return "en"
        return "ru"


class BaseListLangAPIView(BaseLangAPIView):
    not_found_name: str = None
    list_base_cache_name: str = None

    def list(self, request, *args, **kwargs):
        page = request.query_params.get('page', 1)

        cache_key = f'{self.list_base_cache_name}_list_{self.lang}_page_{page}'
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            raise NotFound(self.not_found_name)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = serializer.data

        cache.set(cache_key, response_data, timeout=60)

        return Response(response_data)


class ProfilesListView(BaseListLangAPIView):
    list_base_cache_name = "profiles"
    not_found_name = "Profiles not found"
    serializer_class = ProfileSerializer

    def get_serializer(self, *args, **kwargs):
        lang = self.get_exclude_lang()

        kwargs['exclude_fields'] = ('files', 'tasks', f'description_{lang}', f'description_{lang}_html')

        serializer = self.get_serializer_class()
        return serializer(*args, **kwargs)

    def get_queryset(self):
        return Profile.objects.prefetch_related('tasks')

    def get(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        self.log_user_action("Viewed profile list")

        return response


class ProfileRetrieveView(RetrieveModelMixin, BaseLangAPIView):
    serializer_class = ProfileSerializer

    def get_serializer(self, *args, **kwargs):
        lang = self.get_exclude_lang()

        kwargs['exclude_fields'] = ('user_id', 'files', f'description_{lang}', f'description_{lang}_html')
        serializer = self.get_serializer_class()
        return serializer(*args, **kwargs)

    def get_object(self):
        profile_id = self.kwargs.get("profileId")
        profile = get_object_or_404(Profile.objects.prefetch_related('tasks'), id=profile_id)
        self.check_object_permissions(self.request, profile)
        return profile

    def get(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("profileId")
        cache_key = f"profile_{self.lang}_{profile_id}"
        cached_response = cache.get(cache_key)

        if cached_response:
            self.log_user_action(f"Retrieved profile {profile_id}")
            return Response(cached_response)

        response = self.retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=60)

        self.log_user_action(f"Retrieved profile {profile_id}")

        return response


class TasksListView(BaseListLangAPIView):
    list_base_cache_name = "tasks"
    not_found_name = "No tasks found matching the given criteria"
    lookup_url_kwarg = "profileId"
    filterset_class = TasksFilter
    serializer_class = TaskSerializer
    ordering = ('id',)

    def get_queryset(self):
        profile_id = self.kwargs.get('profileId')
        queryset = Task.objects.select_related('profile_id').prefetch_related('submissions').filter(profile_id=profile_id)
        return queryset

    def get_serializer(self, *args, **kwargs):
        lang = self.get_exclude_lang()
        kwargs['exclude_fields'] = (
            'profile', 'submissions', f'title_{lang}', f'description_{lang}', f'description_{lang}_html', 'profile_id')
        serializer = self.get_serializer_class()
        return serializer(*args, **kwargs)

    def get_ordering_fields(self):
        fields = ['id', 'status', 'type', 'submissions_count', f'title_{self.lang}']
        return fields

    def get(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        self.log_user_action(f"Viewed tasks list for profile {self.kwargs.get('profileId')}")
        return response


class TaskRetrieveView(RetrieveModelMixin, BaseLangAPIView):
    serializer_class = TaskSerializer
    permission_classes = (IsProfileOwnerOrReadOnly, TaskNotDonePermission)
    lookup_url_kwarg = 'taskId'

    def get_queryset(self):
        return Task.objects.select_related('profile_id').prefetch_related('submissions')

    def get_serializer(self, *args, **kwargs):
        lang = self.get_exclude_lang()
        kwargs['exclude_fields'] = (f'title_{lang}', f'description_{lang}', f'description_{lang}_html')

        serializer = self.get_serializer_class()

        return serializer(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        task_id = self.kwargs.get('taskId')
        cache_key = f"task_{self.lang}_{task_id}"
        cached_response = cache.get(cache_key)

        if cached_response:
            self.log_user_action(f"Retrieved task {task_id}")
            return Response(cached_response)

        response = self.retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=60)

        self.log_user_action(f"Retrieved task {task_id}")
        return response


class SubmissionCreateUpdateRetrieveView(UserActionLogMixin, CreateModelMixin, UpdateModelMixin, RetrieveModelMixin,
                                          GenericAPIView):
    lookup_url_kwarg = 'taskId'
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    permission_classes = (IsProfileOwnerOrReadOnly, SubmissionTaskNotDonePermission)
    filterset_class = SubmissionsFilter
    ordering_fields = ('status',)

    def get_queryset(self):
        return Submission.objects.select_related('task_id').only('task_id__status', 'comment')

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, user_id=self.request.user, task_id=self.kwargs.get('taskId'))
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer(self, *args, **kwargs):
        method = self.request.method

        if method == 'GET':
            kwargs['exclude_fields'] = ('change_history', 'id')
            return SubmissionSerializer(*args, **kwargs)
        if method in ('POST', 'PUT', 'PATCH'):
            return SubmissionCreateUpdateSerializer(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        response = self.retrieve(request, *args, **kwargs)

        self.log_user_action(f"Viewed himself submission for task {self.kwargs.get('taskId')}")
        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = self.kwargs.get('taskId')
        task = get_object_or_404(Task, id=task_id)

        if task.status == 'DONE':
            raise PermissionDenied("This task is already completed and cannot be accessed.")

        user = self.request.user

        if Submission.objects.filter(task_id=task_id, user_id=user).exists():
            raise DuplicateSubmissionError()

        serializer.context['task'] = task
        serializer.context['user'] = user

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        self.log_user_action(f"Created submission for task {self.kwargs.get('taskId')}")

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user = serializer.context.get('user')
        task = serializer.context.get('task')
        serializer.save(
            user_id=user,
            task_id=task
        )

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        self.log_user_action(f"Updated submission for task {self.kwargs.get('taskId')}")

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)