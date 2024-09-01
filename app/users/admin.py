from django.contrib import admin
from .models import UserActionLog


class UserActionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')  # Отображение полей в списке
    list_filter = ('user',)  # Фильтр по пользователю
    ordering = ('-timestamp',)  # Сортировка по времени, последнее действие сверху


@admin.register(UserActionLog)
class Admin(UserActionLogAdmin):
    pass
