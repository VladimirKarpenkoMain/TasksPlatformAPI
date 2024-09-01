import markdown
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.generics import get_object_or_404

from .models import Profile, Task, Submission, SubmissionHistory, ProfileFile, TaskSubmission, TaskProfile
from django.conf import settings
from rest_framework.exceptions import ValidationError

User = get_user_model()


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        # Поля для включения/исключения
        exclude_fields = kwargs.pop('exclude_fields', None)

        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        # Если указаны exclude_fields, то удаляем эти поля
        if exclude_fields is not None:
            for field_name in exclude_fields:
                self.fields.pop(field_name, None)


class ProfileFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileFile
        fields = ('file',)


class SubmissionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionHistory
        fields = ['id', 'changed_at', 'previous_comment', 'previous_admin_comment', 'previous_status']
        read_only_fields = ['id']


class SubmissionSerializer(DynamicFieldsModelSerializer):
    change_history = SubmissionHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = ('id', 'user_id', 'status', 'comment', 'admin_comment', 'change_history')
        read_only_fields = ['id']


class SubmissionAdminUpdateSerializer(DynamicFieldsModelSerializer):
    status = serializers.CharField(required=True)
    admin_comment = serializers.CharField(required=True)

    class Meta:
        model = Submission
        fields = ('status', 'admin_comment')
        read_only_fields = ['id']


class FilteredSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        read_only_fields = ['id']
        exclude = ['change_history', 'task_id', 'comment', 'admin_comment']


class GroupedSubmissionSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    submissions = FilteredSubmissionSerializer(many=True)


class ProfileSerializer(DynamicFieldsModelSerializer):
    files = ProfileFileSerializer(many=True, read_only=True)
    tasks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField(method_name='get_count_tasks', read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=1000000, allow_empty_file=False, use_url=False),
        max_length=settings.PROFILE_MAX_NUMBER_FILES,
        write_only=True,
        required=False
    )
    description_ru_html = serializers.SerializerMethodField(method_name='get_description_ru_html')
    description_en_html = serializers.SerializerMethodField(method_name='get_description_en_html')

    class Meta:
        model = Profile
        fields = ('id', 'description_ru', 'description_en', 'description_ru_html',
                  'description_en_html', 'files', 'tasks', 'tasks_count', 'uploaded_files')
        read_only_fields = ['id']

    def get_count_tasks(self, obj):
        return obj.tasks.count()

    def get_description_ru_html(self, obj):
        return markdown.markdown(obj.description_ru)

    def get_description_en_html(self, obj):
        return markdown.markdown(obj.description_en)

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        profile = Profile.objects.create(**validated_data)

        self._handle_file_upload(profile, uploaded_files)

        return profile

    def update(self, instance, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])

        if uploaded_files:
            for profile_file in instance.files.all():
                profile_file.file.delete()  # Удаляет сам файл
                profile_file.delete()

        if len(uploaded_files) + instance.files.count() > settings.PROFILE_MAX_NUMBER_FILES:
            raise ValidationError(
                {"detail": f"Total number of files exceeded, maximum is {settings.PROFILE_MAX_NUMBER_FILES}"})

        self._handle_file_upload(instance, uploaded_files)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def _handle_file_upload(self, profile, uploaded_files):
        for file in uploaded_files:
            if file.size <= settings.PROFILE_MAX_FILE_SIZE:
                ProfileFile.objects.create(profile=profile, file=file)
            else:
                raise ValidationError({
                    "detail": f"File '{file.name}' size exceeded, maximum size {settings.PROFILE_MAX_FILE_SIZE / (1024 * 1024)} MB"})


class TaskSerializer(DynamicFieldsModelSerializer):
    task_exclude_fields = ['id', 'task_id', 'description_ru', 'description_en', 'description_ru_html',
                           'description_en_html', 'description_ru_html', 'description_en_html', 'tasks', 'tasks_count']
    profile = ProfileSerializer(read_only=True, source='profile_id', exclude_fields=task_exclude_fields)
    description_ru_html = serializers.SerializerMethodField(method_name='get_description_ru_html')
    description_en_html = serializers.SerializerMethodField(method_name='get_description_en_html')
    submissions_count = serializers.SerializerMethodField(method_name='get_count_submissions')

    def get_count_submissions(self, obj):
        return obj.submissions.count()

    def get_description_ru_html(self, obj):
        return markdown.markdown(obj.description_ru)

    def get_description_en_html(self, obj):
        return markdown.markdown(obj.description_en)

    class Meta:
        model = Task
        fields = ('id', 'profile_id', 'title_ru', 'title_en', 'description_ru', 'description_en', 'description_ru_html',
                  'description_en_html', 'status', 'type', 'submissions_count', 'profile')
        read_only_fields = ['id']

    def create(self, validated_data):
        task = Task.objects.create(**validated_data)

        task_profile = TaskProfile.objects.create(
            profile=validated_data.get('profile_id'),
            task=task
        )

        task_profile.save()

        return task


class ProfileChangeSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField()
    user_id = serializers.UUIDField()

    class Meta:
        fields = ('profile_id', 'user_id',)

    def validate(self, data):
        user = get_object_or_404(User, id=data['user_id'])
        profile = get_object_or_404(Profile, id=data['profile_id'])
        data['user'] = user
        data['profile'] = profile
        return data


class SubmissionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['comment']  # Ограничиваем поля, которые можно передавать

    def create(self, validated_data):
        # Извлечение user и task_id из контекста
        user = self.context['user']
        task = self.context['task']

        # Создание объекта Submission с извлеченными и валидированными данными
        submission = Submission.objects.create(
            user_id=user,
            task_id=task,
            comment=validated_data['comment'],
            status=Submission.Status.WAITING
        )

        task_submission = TaskSubmission.objects.create(
            task=task,
            submission=submission
        )
        task_submission.save()

        return submission

    def update(self, instance, validated_data):
        submission_history = SubmissionHistory.objects.create(
            submission=instance,
            previous_comment=instance.comment,
            previous_admin_comment=instance.admin_comment,
            previous_status=instance.status
        )
        submission_history.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.change_history.add(submission_history)
        instance.save()

        return instance
