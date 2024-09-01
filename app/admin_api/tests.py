import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import UserProfile, Profile, Task, Submission, TaskSubmission
from api.serializers import ProfileSerializer, TaskSerializer
from .factories import UserFactory, ProfileFactory, UserProfileFactory
from .permissions import IsAdmin
from .views import AdminRetrieveUpdateDestroyProfileView, AdminRetrieveUpdateDestroyTaskView

from users.models import UserActionLog
from datetime import datetime, timedelta

User = get_user_model()


class AdminUsersListViewTest(APITestCase):
    def setUp(self):
        self.admin_user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.url = reverse('users', kwargs={'lang': 'en'})  # or 'ru' depending on your test needs
        self.users = UserFactory.create_batch(10)
        for user in self.users:
            profiles = ProfileFactory.create_batch(2, user=user)
            for profile in profiles:
                UserProfileFactory(user=user, profile=profile)

    def test_list_users(self):
        response = self.client.get(self.url)
        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(data.get('results')), 11)  # 10 users + 1 admin
        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertIn('previous', data)

    def test_filter_by(self):
        base = {'id': self.users[0].id,
                'username': self.users[0].username,
                'email': self.users[0].email
                }
        for key in base:
            response = self.client.get(f"{self.url}?{key}={base[key]}")
            data = response.json().get('results')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0][f'{key}'], str(base[key]))

    def test_filter_by_profiles_count(self):
        response = self.client.get(f"{self.url}?profiles_count=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(user['profiles_count'] == 2 for user in response.json()['results']))

    def test_filter_profiles_count_gte(self):
        response = self.client.get(f"{self.url}?profiles_count_gte=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(user['profiles_count'] >= 2 for user in response.json()['results']))

    def test_filter_profiles_count_lte(self):
        response = self.client.get(f"{self.url}?profiles_count_lte=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(user['profiles_count'] <= 2 for user in response.json()['results']))

    def test_ordering(self):
        response = self.client.get(f"{self.url}?ordering=-username")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [user['username'] for user in response.data['results']]
        self.assertEqual(usernames, sorted(usernames, reverse=True))

    def test_combined_filter_and_ordering(self):
        response = self.client.get(f"{self.url}?profiles_count=2&ordering=-email")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(user['profiles_count'] == 2 for user in response.data['results']))
        emails = [user['email'] for user in response.data['results']]
        self.assertEqual(emails, sorted(emails, reverse=True))

    def test_permission_denied(self):
        self.client.force_authenticate(user=UserFactory())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_fields = ['id', 'username', 'email', 'profiles_count']
        self.assertTrue(all(field in response.data['results'][0] for field in expected_fields))


class AdminUserViewSetTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Test Profile', description_en='Test Profile')

        # Аутентификация админа
        refresh = RefreshToken.for_user(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_set_profile_success(self):
        url = reverse('admin-user-set-profile', kwargs={'lang': 'en'})
        data = {
            'user_id': str(self.regular_user.id),
            'profile_id': str(self.profile.id)
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(UserProfile.objects.filter(user=self.regular_user, profile=self.profile).exists())

    def test_set_profile_already_exists(self):
        UserProfile.objects.create(user=self.regular_user, profile=self.profile)
        url = reverse('admin-user-set-profile', kwargs={'lang': 'ru'})
        data = {
            'user_id': str(self.regular_user.id),
            'profile_id': str(self.profile.id)
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_set_password_success(self):
        url = reverse('admin-user-set-password', kwargs={'lang': 'ru'})
        data = {
            'user_id': str(self.regular_user.id),
            'new_password': 'newpassword123'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.check_password('newpassword123'))

    def test_set_password_user_not_found(self):
        url = reverse('admin-user-set-password', kwargs={"lang": "ru"})
        data = {
            'user_id': '00000000-0000-0000-0000-000000000000',  # несуществующий UUID
            'new_password': 'newpassword123'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_password_invalid_data(self):
        url = reverse('admin-user-set-password', kwargs={"lang": "ru"})
        data = {
            'user_id': str(self.regular_user.id),
            'new_password': 'short'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthorized_access(self):
        # Удаляем аутентификацию
        self.client.credentials()

        url = reverse('admin-user-set-profile', kwargs={"lang": "ru"})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        url = reverse('admin-user-set-password', kwargs={"lang": "ru"})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminProfileListCreateViewTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        refresh = RefreshToken.for_user(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.url = reverse('admin-profiles', kwargs={'lang': 'en'})
        cache.clear()

    def test_list_profiles(self):
        Profile.objects.create(description_ru='Profile 1', description_en='Profile 1')
        Profile.objects.create(description_ru='Profile 2', description_en='Profile 2')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_create_profile(self):
        data = {'description_ru': 'New Profile', 'description_en': 'New Profile'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Profile.objects.count(), 1)

    def test_caching(self):
        Profile.objects.create(description_ru='Profile 1', description_en='Profile 1')

        response1 = self.client.get(self.url)
        response2 = self.client.get(self.url)

        self.assertEqual(response1.data, response2.data)
        self.assertIn('Cache-Control', response2.headers)

    def test_ordering(self):
        Profile.objects.create(description_ru='Profile 1', description_en='Profile 1')
        Profile.objects.create(description_ru='Profile 2', description_en='Profile 2')

        response = self.client.get(f'{self.url}?ordering=-id')
        self.assertEqual(response.data['results'][0]['description_en'], 'Profile 2')

    def test_filtering(self):
        Profile.objects.create(description_ru='Profile 1', description_en='Profile 1')
        Profile.objects.create(description_ru='Profile 2', description_en='Profile 2')

        response = self.client.get(f'{self.url}?id={Profile.objects.first().id}')
        self.assertEqual(len(response.data['results']), 1)

    def test_language_exclusion(self):
        Profile.objects.create(description_ru='Profile RU', description_en='Profile EN')

        response = self.client.get(self.url)
        self.assertNotIn('description_ru', response.data['results'][0])
        self.assertIn('description_en', response.data['results'][0])

    def test_unauthorized_access(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminRetrieveUpdateDestroyProfileViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', description_en="EN", description_ru="RU",
                                        profile_id=self.profile)
        self.url = reverse('admin-profile-detail', kwargs={'profileId': self.profile.id, 'lang': 'en'})

    def test_retrieve_profile_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(uuid.UUID(response.data['id']), self.profile.id)

    def test_retrieve_profile_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_nonexistent_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-profile-detail', kwargs={'profileId': uuid.uuid4(), 'lang': 'en'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_profile_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {'description_ru': 'Обновленный профиль', 'description_en': 'Updated profile'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description_ru, 'Обновленный профиль')

    def test_partial_update_profile_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {'description_ru': 'Частично обновленный профиль'}
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description_ru, 'Частично обновленный профиль')

    def test_update_profile_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {'description_ru': 'Обновленный профиль'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_profile_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profile.objects.filter(id=self.profile.id).exists())

    def test_delete_profile_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prefetch_related_tasks(self):
        self.client.force_authenticate(user=self.admin_user)
        with self.assertNumQueries(2):  # 1 для профиля, 1 для связанных задач
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tasks', response.data)

    def test_serializer_class(self):
        view = AdminRetrieveUpdateDestroyProfileView()
        self.assertEqual(view.serializer_class, ProfileSerializer)

    def test_permission_classes(self):
        view = AdminRetrieveUpdateDestroyProfileView()
        self.assertEqual(view.permission_classes, (IsAdmin,))

    def test_lookup_url_kwarg(self):
        view = AdminRetrieveUpdateDestroyProfileView()
        self.assertEqual(view.lookup_url_kwarg, "profileId")

    def test_add_files_to_profile(self):
        self.client.force_authenticate(user=self.admin_user)

        # Создаем тестовые файлы
        file1 = SimpleUploadedFile("file1.txt", b"file_content", content_type="text/plain")
        file2 = SimpleUploadedFile("file2.txt", b"file_content" * 1000, content_type="text/plain")

        data = {
            'description_ru': 'Профиль с файлами',
            'description_en': 'Profile with files',
            'uploaded_files': [file1, file2]
        }

        response = self.client.put(self.url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()
        self.assertLessEqual(self.profile.files.count(),
                             settings.PROFILE_MAX_NUMBER_FILES)  # Только один файл должен быть загружен

        # Проверяем, что файл не превышает максимальный размер
        uploaded_file = self.profile.files.first()
        self.assertLessEqual(uploaded_file.file.size, settings.PROFILE_MAX_FILE_SIZE)

        # Пытаемся загрузить больше файлов, чем разрешено
        max_files = settings.PROFILE_MAX_NUMBER_FILES
        files = [SimpleUploadedFile(f"file{i}.txt", b"content") for i in range(max_files + 1)]

        data['uploaded_files'] = files
        response = self.client.put(self.url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Ensure this field has no more than 5 elements.', str(response.data['uploaded_files']))

        # Очистка: удаляем загруженные файлы
        base = self.profile.files.first().file.path[:-10]

        for profile_file in self.profile.files.all():
            if os.path.exists(profile_file.file.path):
                os.remove(profile_file.file.path)
        os.rmdir(base)


class AdminTaskListCreateViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(
            title_ru='Задача',
            title_en='Task',
            description_ru='Описание',
            description_en='Description',
            profile_id=self.profile
        )
        self.url = reverse('admin-tasks', kwargs={'lang': 'en'})

    def test_list_tasks_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_tasks_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_task_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title_ru': 'Новая задача',
            'title_en': 'New task',
            'description_ru': 'Новое описание',
            'description_en': 'New description',
            'profile_id': self.profile.id
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.count(), 2)

    def test_create_task_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {
            'title_ru': 'Новая задача',
            'title_en': 'New task',
            'description_ru': 'Новое описание',
            'description_en': 'New description',
            'profile_id': self.profile.id
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_task_with_invalid_data(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title_ru': '',
            'title_en': '',
            'description_ru': 'Новое описание',
            'description_en': 'New description',
            'profile_id': str(self.profile.id)
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_queryset(self):
        self.client.force_authenticate(user=self.admin_user)
        sub = Submission.objects.create(task_id=self.task, user_id=self.admin_user)
        TaskSubmission.objects.create(task=self.task, submission=sub)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['submissions_count'], 1)

    def test_get_serializer_for_get_request(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('title_ru', response.data['results'][0])
        self.assertNotIn('description_ru', response.data['results'][0])
        self.assertNotIn('description_ru_html', response.data['results'][0])

    def test_get_ordering_fields(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.url}?ordering=-id")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caching(self):
        self.client.force_authenticate(user=self.admin_user)
        cache.clear()

        # First request should hit the database
        with self.assertNumQueries(3):  # Adjust this number based on your actual query count
            response1 = self.client.get(self.url)

        # Second request should use cache
        with self.assertNumQueries(0):
            response2 = self.client.get(self.url)

        self.assertEqual(response1.data, response2.data)

        # Create a new task to invalidate cache
        Task.objects.create(
            title_ru='Новая задача',
            title_en='New task',
            description_ru='Новое описание',
            description_en='New description',
            profile_id=self.profile
        )

        # This request should hit the database again
        with self.assertNumQueries(3):  # Adjust this number based on your actual query count
            response3 = self.client.get(self.url)

        self.assertNotEqual(response2.data, response3.data)


class AdminRetrieveUpdateDestroyTaskViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(
            title_ru='Задача',
            title_en='Task',
            description_ru='Описание',
            description_en='Description',
            profile_id=self.profile
        )
        self.url = reverse('admin-task-detail', kwargs={'taskId': self.task.id, 'lang': 'ru'})

    def test_retrieve_task_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.task.id))

    def test_retrieve_task_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_task_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'title_ru': 'Обновленная задача',
            'title_en': 'Updated task',
            'description_ru': 'Обновленное описание',
            'description_en': 'Updated description',
            'profile_id': self.profile.id
        }
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title_ru, 'Обновленная задача')

    def test_partial_update_task_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {'title_ru': 'Частично обновленная задача'}
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title_ru, 'Частично обновленная задача')

    def test_update_task_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {'title_ru': 'Обновленная задача'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_task_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(id=self.task.id).exists())

    def test_delete_task_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_nonexistent_task(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('admin-task-detail', kwargs={'taskId': uuid.uuid4(), 'lang': 'ru'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_serializer_class(self):
        view = AdminRetrieveUpdateDestroyTaskView()
        self.assertEqual(view.serializer_class, TaskSerializer)

    def test_permission_classes(self):
        view = AdminRetrieveUpdateDestroyTaskView()
        self.assertEqual(view.permission_classes, (IsAdmin,))

    def test_lookup_url_kwarg(self):
        view = AdminRetrieveUpdateDestroyTaskView()
        self.assertEqual(view.lookup_url_kwarg, "taskId")


class AdminSubmissionsListViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', profile_id=self.profile)
        self.submission = Submission.objects.create(task_id=self.task, user_id=self.regular_user, status='WAITING')
        self.url = reverse('admin-submissions', kwargs={'lang': 'ru'})

    def test_list_submissions_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['task_id'], str(self.task.id))

    def test_list_submissions_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_submissions_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_submissions(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.url}?status=WAITING")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_order_submissions(self):
        Submission.objects.create(task_id=self.task, user_id=self.regular_user, status='DONE')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.url}?ordering=-status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['submissions'][0]['status'], 'WAITING')

    def test_grouped_submissions(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('task_id', response.data[0])
        self.assertIn('submissions', response.data[0])


class AdminRetrieveUpdateDestroySubmissionViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', profile_id=self.profile)
        self.submission = Submission.objects.create(task_id=self.task, user_id=self.regular_user, status='WAITING')
        self.url = reverse('admin-submission-detail', kwargs={'submissionId': self.submission.id, 'lang': 'ru'})

    def test_retrieve_submission_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.submission.id))

    def test_retrieve_submission_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_submission_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {'status': 'ACCEPTED'}
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'ACCEPTED')

    def test_delete_submission_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Submission.objects.filter(id=self.submission.id).exists())

    def test_change_history(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('change_history', response.data)


class AdminUserActionLogListViewTest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.user_action_log = UserActionLog.objects.create(user=self.regular_user, action='Test action')
        self.url = reverse('admin-users-logs', kwargs={'lang': 'ru'})

    def test_list_user_action_logs_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_user_action_logs_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_user_action_logs(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.url}?user={self.regular_user.username}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_order_user_action_logs(self):
        UserActionLog.objects.create(user=self.regular_user, action='Another action',
                                     timestamp=datetime.now() + timedelta(days=1))
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"{self.url}?ordering=-timestamp")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['action'], 'Another action')

    def test_pagination(self):
        for i in range(20):
            UserActionLog.objects.create(user=self.regular_user, action=f'Action {i}')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
