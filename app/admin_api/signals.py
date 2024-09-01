from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

User = get_user_model()


# Сигналы для инвалидации кеша
@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    for lang in ['ru', 'en']:
        cache_key_pattern = f'admin_users_list_{lang}_page_*'
        keys = cache.keys(cache_key_pattern)
        cache.delete_many(keys)