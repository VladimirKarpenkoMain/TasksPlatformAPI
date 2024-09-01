from uuid import uuid4

import factory
from django.contrib.auth import get_user_model

from api.models import Profile, Task, UserProfile

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid4)
    username = factory.Faker('user_name')
    email = factory.Faker('email')
    password = factory.PostGenerationMethodCall('set_password', 'password')

    @factory.post_generation
    def profiles(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for profile in extracted:
                self.profiles.add(profile)


class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    description_ru = factory.Faker('text', locale='ru_RU')
    description_en = factory.Faker('text', locale='en_US')

    @factory.post_generation
    def user_id(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for user in extracted:
                self.user_id.add(user)

    @factory.post_generation
    def tasks(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for task in extracted:
                self.tasks.add(task)


class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    profile = factory.SubFactory(ProfileFactory)
