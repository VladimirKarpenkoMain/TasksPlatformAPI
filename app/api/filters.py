import django_filters
from django.db.models import Count

from api.models import Task, Submission


class TasksFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name='id', lookup_expr='exact')
    title = django_filters.CharFilter(method='filter_title')
    submissions_count = django_filters.NumberFilter(method='filter_submissions_count')
    submissions_count_gte = django_filters.NumberFilter(method='filter_submissions_count_gte', lookup_expr='gte')
    submissions_count_lte = django_filters.NumberFilter(method='filter_submissions_count_lte', lookup_expr='lte')

    class Meta:
        model = Task
        fields = {
            'status': ['exact'],
            'type': ['exact'],
        }

    def filter_title(self, queryset, name, value):
        lang = self.request.parser_context['kwargs'].get('lang', 'ru')
        return queryset.filter(**{f'title_{lang}__icontains': value})

    def filter_submissions_count(self, queryset, name, value):
        return queryset.annotate(submissions_count=Count('submissions')).filter(submissions_count=value)

    def filter_submissions_count_gte(self, queryset, name, value):
        return queryset.annotate(submissions_count=Count('submissions')).filter(submissions_count__gte=value)

    def filter_submissions_count_lte(self, queryset, name, value):
        return queryset.annotate(submissions_count=Count('submissions')).filter(submissions_count__lte=value)


class SubmissionsFilter(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name='id', lookup_expr='exact')
    task_id = django_filters.UUIDFilter(field_name='task_id', lookup_expr='exact')
    user_id = django_filters.UUIDFilter(field_name='user_id', lookup_expr='exact')

    class Meta:
        model = Submission
        fields = {
            'status': ['exact'],
        }
