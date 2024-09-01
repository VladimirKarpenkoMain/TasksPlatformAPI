import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.exceptions import DuplicateSubmissionError
from api.models import Profile, Task, Submission, TaskProfile, UserProfile, TaskSubmission
from django.core.cache import cache

User = get_user_model()


class ProfilesListViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.profile1 = Profile.objects.create(description_ru='Тестовый профиль 1', description_en='Test profile 1')
        self.profile2 = Profile.objects.create(description_ru='Тестовый профиль 2', description_en='Test profile 2')
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', profile_id=self.profile1)
        self.url = reverse('profiles', kwargs={'lang': 'ru'})

    def test_list_profiles(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_exclude_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertNotIn('files', response.data['results'][0])
        self.assertNotIn('tasks', response.data['results'][0])
        self.assertNotIn('description_en', response.data['results'][0])
        self.assertNotIn('description_en_html', response.data['results'][0])

    def test_include_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('description_ru', response.data['results'][0])
        self.assertIn('description_ru_html', response.data['results'][0])

    def test_prefetch_related(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(4):  # 1 для профилей, 1 для связанных задач
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caching(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()

        # Первый запрос должен обратиться к базе данных
        with self.assertNumQueries(4):
            response1 = self.client.get(self.url)

        # Второй запрос должен использовать кеш
        with self.assertNumQueries(1):
            response2 = self.client.get(self.url)

        self.assertEqual(response1.data, response2.data)

    def test_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_correct_serializer(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Проверяем, что используется правильный сериализатор
        self.assertIn('id', response.data['results'][0])
        self.assertIn('description_ru', response.data['results'][0])

    def test_pagination(self):
        for i in range(10):
            Profile.objects.create(description_ru=f'Профиль {i}', description_en=f'Profile {i}')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertTrue(len(response.data['results']) <= 20)  # предполагая, что размер страницы по умолчанию 10

    def test_language_response(self):
        self.client.force_authenticate(user=self.user)
        response_ru = self.client.get(reverse('profiles', kwargs={'lang': 'ru'}))
        response_en = self.client.get(reverse('profiles', kwargs={'lang': 'en'}))
        self.assertNotEqual(response_ru.data['results'][0]['description_ru'],
                            response_en.data['results'][0]['description_en'])

    def test_sorting_order(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        ids = [profile['id'] for profile in response.data['results']]
        self.assertEqual(ids, sorted(ids))  # проверяем, что профили отсортированы по id


class ProfileRetrieveViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', profile_id=self.profile)
        self.url = reverse('profile-detail', kwargs={'lang': 'ru', 'profileId': self.profile.id})

    def test_retrieve_profile(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.profile.id))

    def test_exclude_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertNotIn('user_id', response.data)
        self.assertNotIn('files', response.data)
        self.assertNotIn('description_en', response.data)
        self.assertNotIn('description_en_html', response.data)

    def test_include_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('description_ru', response.data)
        self.assertIn('description_ru_html', response.data)

    def test_prefetch_related(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(3):  # 1 for profile, 1 for related tasks
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caching(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()

        # First request should hit the database
        with self.assertNumQueries(3):
            response1 = self.client.get(self.url)

        # Second request should use cache
        with self.assertNumQueries(1):
            response2 = self.client.get(self.url)

        self.assertEqual(response1.data, response2.data)

    def test_cache_invalidation(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()

        response1 = self.client.get(self.url)

        # Update profile
        self.profile.description_ru = 'Updated description'
        self.profile.save()

        response2 = self.client.get(self.url)

        self.assertNotEqual(response1.data['description_ru'], response2.data['description_ru'])

    def test_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('profile-detail', kwargs={'lang': 'ru', 'profileId': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_language_response(self):
        self.client.force_authenticate(user=self.user)
        response_ru = self.client.get(reverse('profile-detail', kwargs={'lang': 'ru', 'profileId': self.profile.id}))
        response_en = self.client.get(reverse('profile-detail', kwargs={'lang': 'en', 'profileId': self.profile.id}))
        self.assertIn('description_ru', response_ru.data)
        self.assertIn('description_en', response_en.data)

    def test_correct_serializer(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that the correct serializer is used
        self.assertIn('id', response.data)
        self.assertIn('description_ru', response.data)


class TasksListViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        UserProfile.objects.create(user=self.user, profile=self.profile)
        self.task1 = Task.objects.create(title_ru='Задача 1', title_en='Task 1', profile_id=self.profile,
                                         status='AVAILABLE',
                                         type='FREE')
        self.task2 = Task.objects.create(title_ru='Задача 2', title_en='Task 2', profile_id=self.profile,
                                         status='CLOSED', type='SPECIFIC')
        TaskProfile.objects.create(task=self.task1, profile=self.profile)
        TaskProfile.objects.create(task=self.task2, profile=self.profile)
        self.submission = Submission.objects.create(task_id=self.task1, user_id=self.user)
        TaskSubmission.objects.create(task=self.task1, submission=self.submission)
        self.url = reverse('tasks', kwargs={'lang': 'ru', 'profileId': self.profile.id})

    def test_list_tasks(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_filter_tasks(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{self.url}?status=AVAILABLE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'AVAILABLE')

    def test_exclude_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertNotIn('profile', response.data['results'][0])
        self.assertNotIn('submissions', response.data['results'][0])
        self.assertNotIn('title_en', response.data['results'][0])
        self.assertNotIn('description_en', response.data['results'][0])
        self.assertNotIn('description_en_html', response.data['results'][0])
        self.assertNotIn('profile_id', response.data['results'][0])

    def test_include_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('title_ru', response.data['results'][0])
        self.assertIn('description_ru', response.data['results'][0])
        self.assertIn('description_ru_html', response.data['results'][0])

    def test_prefetch_related(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(5):  # 1 for tasks, 1 for related submissions
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caching(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()

        # First request should hit the database
        with self.assertNumQueries(5):
            response1 = self.client.get(self.url)

        # Second request should use cache
        with self.assertNumQueries(1):
            response2 = self.client.get(self.url)

        self.assertEqual(response1.data, response2.data)

    def test_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('tasks', kwargs={'lang': 'ru', 'profileId': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_language_response(self):
        self.client.force_authenticate(user=self.user)
        response_ru = self.client.get(reverse('tasks', kwargs={'lang': 'ru', 'profileId': self.profile.id}))
        response_en = self.client.get(reverse('tasks', kwargs={'lang': 'en', 'profileId': self.profile.id}))
        self.assertIn('title_ru', response_ru.data['results'][0])
        self.assertIn('title_en', response_en.data['results'][0])

    def test_ordering_fields(self):
        self.client.force_authenticate(user=self.user)
        for field in ['id', 'status', 'type', 'submissions_count', 'title_ru']:
            response = self.client.get(f"{self.url}?ordering={field}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class TaskRetrieveViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        UserProfile.objects.create(user=self.user, profile=self.profile)
        self.task = Task.objects.create(
            title_ru='Задача',
            title_en='Task',
            description_ru='Описание',
            description_en='Description',
            profile_id=self.profile,
            status='AVAILABLE',
            type='FREE'
        )
        TaskProfile.objects.create(task=self.task, profile=self.profile)
        self.submission = Submission.objects.create(task_id=self.task, user_id=self.user)
        TaskSubmission.objects.create(task=self.task, submission=self.submission)
        self.url = reverse('task-detail', kwargs={'lang': 'ru', 'taskId': self.task.id})

    def test_retrieve_task(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.task.id))

    def test_exclude_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertNotIn('title_en', response.data)
        self.assertNotIn('description_en', response.data)
        self.assertNotIn('description_en_html', response.data)

    def test_include_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('title_ru', response.data)
        self.assertIn('description_ru', response.data)
        self.assertIn('description_ru_html', response.data)

    def test_cache_invalidation(self):
        self.client.force_authenticate(user=self.user)
        cache.clear()

        response1 = self.client.get(self.url)

        self.task.title_ru = 'Updated Task'
        self.task.save()

        response2 = self.client.get(self.url)

        self.assertNotEqual(response1.data['title_ru'], response2.data['title_ru'])

    def test_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_permission_profile_owner(self):
        other_user = User.objects.create_user('otheruser', 'other@example.com', 'otherpass')
        self.client.force_authenticate(user=other_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permission_task_not_done(self):
        self.task.status = 'DONE'
        self.task.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_task(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('task-detail', kwargs={'lang': 'ru', 'taskId': uuid.uuid4()})
        response = self.client.get(url)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_language_response(self):
        self.client.force_authenticate(user=self.user)
        response_ru = self.client.get(reverse('task-detail', kwargs={'lang': 'ru', 'taskId': self.task.id}))
        response_en = self.client.get(reverse('task-detail', kwargs={'lang': 'en', 'taskId': self.task.id}))
        self.assertIn('title_ru', response_ru.data)
        self.assertIn('title_en', response_en.data)

    def test_submissions_included(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertIn('submissions_count', response.data)
        self.assertEqual(response.data['submissions_count'], 1)


class SubmissionCreateUpdateRetrieveViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.profile = Profile.objects.create(description_ru='Тестовый профиль', description_en='Test profile')
        UserProfile.objects.create(user=self.user, profile=self.profile)
        self.task = Task.objects.create(title_ru='Задача', title_en='Task', profile_id=self.profile, status='AVAILABLE')
        TaskProfile.objects.create(task=self.task, profile=self.profile)
        self.submission = Submission.objects.create(task_id=self.task, user_id=self.user, comment='Initial comment')
        TaskSubmission.objects.create(submission=self.submission, task=self.task)
        self.url = reverse('submission-detail', kwargs={'taskId': self.task.id, 'lang': 'ru'})

    def test_retrieve_submission(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['comment'], 'Initial comment')
        self.assertNotIn('change_history', response.data)
        self.assertNotIn('id', response.data)

    def test_create_submission(self):
        self.client.force_authenticate(user=self.user)
        new_task = Task.objects.create(title_ru='Новая задача', title_en='New Task', profile_id=self.profile,
                                       status='AVAILABLE')
        TaskProfile.objects.create(task=new_task, profile=self.profile)
        url = reverse('submission-detail', kwargs={'taskId': new_task.id, 'lang': 'ru'})
        data = {'comment': 'New submission'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Submission.objects.count(), 2)

    def test_update_submission(self):
        self.client.force_authenticate(user=self.user)
        data = {'comment': 'Updated comment'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.comment, 'Updated comment')

    def test_partial_update_submission(self):
        self.client.force_authenticate(user=self.user)
        data = {'comment': 'Partially updated comment'}
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.comment, 'Partially updated comment')

    def test_duplicate_submission(self):
        self.client.force_authenticate(user=self.user)
        data = {'comment': 'Duplicate submission'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertRaises(DuplicateSubmissionError)

    def test_retrieve_nonexistent_submission(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('submission-detail', kwargs={'taskId': uuid.uuid4(), 'lang': 'ru'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_submission_unauthenticated(self):
        data = {'comment': 'Unauthenticated submission'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_submission_unauthenticated(self):
        data = {'comment': 'Unauthenticated update'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_submission_wrong_user(self):
        other_user = User.objects.create_user('otheruser', 'other@example.com', 'otherpass')
        self.client.force_authenticate(user=other_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_submission_wrong_user(self):
        other_user = User.objects.create_user('otheruser', 'other@example.com', 'otherpass')
        self.client.force_authenticate(user=other_user)
        data = {'comment': 'Wrong user update'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_submission_done_task(self):
        self.task.status = 'DONE'
        self.task.save()
        self.client.force_authenticate(user=self.user)
        data = {'comment': 'Submission for done task'}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_submission_done_task(self):
        self.task.status = 'DONE'
        self.task.save()
        self.client.force_authenticate(user=self.user)
        data = {'comment': 'Update for done task'}
        response = self.client.put(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_submissions(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{self.url}?status=PENDING")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_order_submissions(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"{self.url}?ordering=-status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
