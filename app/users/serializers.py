from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers

from users.models import UserActionLog

User = get_user_model()


class DynamicFieldsUserSerializer(BaseUserSerializer):
    def __init__(self, *args, **kwargs):
        # Поля для включения/исключения
        exclude_fields = kwargs.pop('exclude_fields', None)

        super(DynamicFieldsUserSerializer, self).__init__(*args, **kwargs)

        # Если указаны exclude_fields, то удаляем эти поля
        if exclude_fields is not None:
            for field_name in exclude_fields:
                self.fields.pop(field_name, None)


class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('username', 'email', 'password', 'profiles')


class UserChangePasswordSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    new_password = serializers.CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        fields = ('user_id', 'new_password',)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("The password must be at least 8 characters")
        return value


class UserSerializer(DynamicFieldsUserSerializer):
    profiles_count = serializers.SerializerMethodField(method_name='get_count_profiles')

    class Meta(BaseUserSerializer.Meta):
        model = User
        fields = ('id', 'username', 'email', 'profiles', 'profiles_count')
        read_only_fields = ['id']

    def get_count_profiles(self, obj):
        return obj.profiles.count()
