from rest_framework import serializers

from users.models import UserActionLog


class UserActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActionLog
        fields = '__all__'
