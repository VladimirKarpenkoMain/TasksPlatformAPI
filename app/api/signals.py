from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from api.models import Profile, Task


# Сигналы для инвалидации кеша
@receiver(post_save, sender=Profile)
@receiver(post_delete, sender=Profile)
def invalidate_profile_cache(sender, instance, **kwargs):

    for lang in ['ru', 'en']:
        cache_key = f"profile_{lang}_{instance.id}"
        cache.delete(cache_key)
        patterns = (f'profiles_list_{lang}_page_*', f"admin_profiles_list_{lang}_page_*")
        for pattern in patterns:
            keys = cache.keys(pattern)
            cache.delete_many(keys)

# Сигналы для инвалидации кеша
@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def invalidate_task_cache(sender, instance, **kwargs):

    for lang in ['ru', 'en']:
        cache_key = f"task_{lang}_{instance.id}"
        cache.delete(cache_key)
        patterns = (f'tasks_list_{lang}_page_*', f'admin_tasks_list_{lang}_page_*')
        for pattern in patterns:
            keys = cache.keys(pattern)
            cache.delete_many(keys)

