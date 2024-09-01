from django.contrib.auth import get_user_model
from django.db import models
from uuid import uuid4

User = get_user_model()


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False, verbose_name="id")
    user_id = models.ManyToManyField(User, verbose_name="ID пользователя", blank=True, through="UserProfile")
    description_ru = models.TextField(verbose_name="Русское описание")
    description_en = models.TextField(verbose_name="Английское описание")
    tasks = models.ManyToManyField('Task', verbose_name="Задачи", through='TaskProfile')

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"
        ordering = ['id']

    def __str__(self):
        return f'Профиль {self.id}'


class Task(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Доступна'
        IN_PROGRESS = 'IN_PROGRESS', 'В ожидании'
        DONE = 'DONE', 'Готова'
        REWORK = 'REWORK', 'На доработке'

    class Type(models.TextChoices):
        FREE = 'FREE', 'Свободная'
        SPECIFIC = 'SPECIFIC', 'Конкретная'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False, verbose_name="id")
    profile_id = models.ForeignKey("Profile", on_delete=models.CASCADE, verbose_name="ID профиля",
                                   related_name="profiles")
    title_ru = models.CharField(max_length=180, verbose_name="Название задачи RU")
    title_en = models.CharField(max_length=180, verbose_name="Название задачи EN")
    description_ru = models.TextField(verbose_name="Описание задачи RU")
    description_en = models.TextField(verbose_name="Описание задачи EN")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE, verbose_name="Статус")
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.FREE, verbose_name="Тип")
    submissions = models.ManyToManyField('Submission', through='TaskSubmission', verbose_name="Ответы",
                                         related_name="submissions_set")

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

    def __str__(self):
        return f'Задача({self.id}) профиля {self.profile_id.id}'


class Submission(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = 'ACCEPTED', 'Принята'
        WAITING = 'WAITING', 'В ожидании'
        REJECTED = 'REJECTED', 'Отклонена'

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь", related_name="users")
    task_id = models.ForeignKey(Task, on_delete=models.CASCADE, verbose_name="ID задачи", related_name="tasks")
    comment = models.TextField(verbose_name="Комментарий")
    admin_comment = models.TextField(null=True, blank=True, verbose_name="Комментарий администратора")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.WAITING, verbose_name="Статус")
    change_history = models.ManyToManyField('SubmissionHistory', related_name='submission_history',
                                            verbose_name="История изменений", blank=True)

    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"


class SubmissionHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, verbose_name="ID ответа")
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name="Время изменения")
    previous_comment = models.TextField(verbose_name="Предыдущий комментарий")
    previous_admin_comment = models.TextField(null=True, blank=True,
                                              verbose_name="Предыдущий комментарий администратора")
    previous_status = models.CharField(max_length=15, choices=Submission.Status.choices,
                                       default=Submission.Status.WAITING, verbose_name="Предыдущий статус")

    class Meta:
        verbose_name = "История ответа"
        verbose_name_plural = "История ответов"


class UserProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, verbose_name="Профиль")

    class Meta:
        verbose_name = "Соответствие профиля и пользователя"
        verbose_name_plural = "Таблица соответствия профиля и пользователя"


class TaskProfile(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, verbose_name="Задача")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, verbose_name="Профиль")

    class Meta:
        verbose_name = "Соответствие профиля и задачи"
        verbose_name_plural = "Таблица соответствия профиля и задач"


class TaskSubmission(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, verbose_name="Задача")
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, verbose_name="Ответ")

    class Meta:
        verbose_name = "Соответствие задачи и ответа"
        verbose_name_plural = "Таблица соответствия задачи и ответа"


class ProfileFile(models.Model):
    def get_upload_path(instance, filename):
        return f'files/{instance.profile.id}/{filename}'

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='files', verbose_name="Профиль")
    file = models.FileField(upload_to=get_upload_path, blank=True, null=True, verbose_name="Файл")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Время загрузки")

    class Meta:
        verbose_name = "Файл профиля"
        verbose_name_plural = "Файлы профиля"

