import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Count
from api.models import Profile
from users.models import UserActionLog

User = get_user_model()


class UsersFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name='id', lookup_expr='exact')
    profiles_count = django_filters.NumberFilter(method='filter_profiles_count')
    profiles_count_gte = django_filters.NumberFilter(method='filter_profiles_count_gte', lookup_expr='gte')
    profiles_count_lte = django_filters.NumberFilter(method='filter_profiles_count_lte', lookup_expr='lte')

    class Meta:
        model = User
        fields = {
            'username': ['exact'],
            'email': ['exact'],
        }

    def filter_profiles_count(self, queryset, name, value):
        return queryset.annotate(profiles_count=Count('profiles')).filter(profiles_count=value)

    def filter_profiles_count_gte(self, queryset, name, value):
        return queryset.annotate(profiles_count=Count('profiles')).filter(profiles_count__gte=value)

    def filter_profiles_count_lte(self, queryset, name, value):
        return queryset.annotate(profiles_count=Count('profiles')).filter(profiles_count__lte=value)


class ProfilesFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name='id', lookup_expr='exact')
    tasks_count = django_filters.NumberFilter(method='filter_tasks_count')
    tasks_count_gte = django_filters.NumberFilter(method='filter_tasks_count_gte', lookup_expr='gte')
    tasks_count_lte = django_filters.NumberFilter(method='filter_tasks_count_lte', lookup_expr='lte')

    class Meta:
        model = Profile
        fields = {}

    def filter_tasks_count(self, queryset, name, value):
        return queryset.annotate(tasks_count=Count('tasks')).filter(tasks_count=value)

    def filter_tasks_count_gte(self, queryset, name, value):
        return queryset.annotate(tasks_count=Count('tasks')).filter(tasks_count__gte=value)

    def filter_tasks_count_lte(self, queryset, name, value):
        return queryset.annotate(tasks_count=Count('tasks')).filter(tasks_count__lte=value)


class UserLogsFilter(django_filters.FilterSet):
    user = django_filters.CharFilter(field_name='user__username', lookup_expr='icontains')

    class Meta:
        model = UserActionLog
        fields = ['user']
