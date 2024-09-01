from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False, verbose_name="ID")
    username = models.CharField(max_length=100, unique=True, verbose_name="Имя пользователя")
    email = models.EmailField(unique=True, verbose_name="Почта пользователя")
    profiles = models.ManyToManyField("api.Profile", verbose_name="Профили пользователя", blank=True, through="api.UserProfile")


class UserActionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    action = models.CharField(max_length=255, verbose_name="Действие")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")
    extra_data = models.JSONField(null=True, blank=True, verbose_name="Дополнительные данные")

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"