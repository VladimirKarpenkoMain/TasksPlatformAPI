from users.models import UserActionLog


class UserActionLogMixin:
    def log_user_action(self, action):
        if self.request.user.is_authenticated:
            UserActionLog.objects.create(
                user=self.request.user,
                action=action,
                extra_data={'path': self.request.path, 'method': self.request.method}
            )