# Generated by Django 5.0.6 on 2024-07-12 18:17

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("api", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="user_id",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="users",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Пользователь",
            ),
        ),
        migrations.AddField(
            model_name="submissionhistory",
            name="submission",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.submission",
                verbose_name="ID ответа",
            ),
        ),
        migrations.AddField(
            model_name="submission",
            name="change_history",
            field=models.ManyToManyField(
                blank=True,
                related_name="submission_history",
                to="api.submissionhistory",
                verbose_name="История изменений",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="profile_id",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="profiles",
                to="api.profile",
                verbose_name="ID профиля",
            ),
        ),
        migrations.AddField(
            model_name="submission",
            name="task_id",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tasks",
                to="api.task",
                verbose_name="ID задачи",
            ),
        ),
        migrations.AddField(
            model_name="taskprofile",
            name="profile",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.profile",
                verbose_name="Профиль",
            ),
        ),
        migrations.AddField(
            model_name="taskprofile",
            name="task",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.task",
                verbose_name="Задача",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="tasks",
            field=models.ManyToManyField(
                through="api.TaskProfile", to="api.task", verbose_name="Задачи"
            ),
        ),
        migrations.AddField(
            model_name="tasksubmission",
            name="submission",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.submission",
                verbose_name="Ответ",
            ),
        ),
        migrations.AddField(
            model_name="tasksubmission",
            name="task",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.task",
                verbose_name="Задача",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="submissions",
            field=models.ManyToManyField(
                related_name="submissions_set",
                through="api.TaskSubmission",
                to="api.submission",
                verbose_name="Ответы",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="profile",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="api.profile",
                verbose_name="Профиль",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
                verbose_name="Пользователь",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="user_id",
            field=models.ManyToManyField(
                blank=True,
                through="api.UserProfile",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ID пользователя",
            ),
        ),
    ]
