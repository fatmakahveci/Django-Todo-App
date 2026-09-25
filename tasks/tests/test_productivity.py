from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task


class ProductivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('planner')
        cls.other = get_user_model().objects.create_user('other-planner')

    def setUp(self):
        self.client.force_login(self.user)

    def test_quick_add_sets_owner_and_defaults(self):
        response = self.client.post(reverse('tasks'), {'title': '  Buy coffee  ', 'user': self.other.pk, 'complete': 'true'})
        self.assertRedirects(response, reverse('tasks'))
        task = Task.objects.get()
        self.assertEqual(task.title, 'Buy coffee')
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.priority, Task.Priority.NORMAL)
        self.assertFalse(task.complete)

    def test_invalid_quick_add_preserves_list_and_shows_error(self):
        Task.objects.create(user=self.user, title='Existing task')
        response = self.client.post(reverse('tasks'), {'title': ' '})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['quick_form'].errors)
        self.assertContains(response, 'Existing task', status_code=400)
        self.assertEqual(Task.objects.count(), 1)

    def test_quick_add_requires_authentication_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('tasks'), {'title': 'No token'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(reverse('tasks'), {'title': 'Anonymous'}).status_code, 302)
        self.assertEqual(Task.objects.count(), 0)

    def test_today_and_next_seven_days_have_precise_boundaries(self):
        today = timezone.localdate()
        for offset in [-1, 0, 1, 7, 8]:
            Task.objects.create(user=self.user, title=f'Day {offset}', due_date=today + timedelta(days=offset))
        Task.objects.create(user=self.user, title='Already done', due_date=today, complete=True)
        Task.objects.create(user=self.other, title='Private', due_date=today)
        response = self.client.get(reverse('tasks'), {'status': 'today'})
        self.assertEqual([t.title for t in response.context['tasks']], ['Day 0'])
        response = self.client.get(reverse('tasks'), {'status': 'upcoming', 'sort': 'due'})
        self.assertEqual([t.title for t in response.context['tasks']], ['Day 1', 'Day 7'])

    def test_due_sort_places_undated_tasks_last(self):
        undated = Task.objects.create(user=self.user, title='No deadline')
        late = Task.objects.create(user=self.user, title='Later', due_date=timezone.localdate() + timedelta(days=4))
        early = Task.objects.create(user=self.user, title='Soon', due_date=timezone.localdate())
        response = self.client.get(reverse('tasks'), {'sort': 'due'})
        self.assertEqual(list(response.context['tasks']), [early, late, undated])
        self.assertEqual(self.client.get(reverse('tasks'), {'sort': 'invalid'}).context['sort'], 'priority')

    def test_completion_keeps_filter_and_recovers_empty_last_page(self):
        tasks = [Task.objects.create(user=self.user, title=f'Task {i}') for i in range(13)]
        url = '/?status=open&sort=oldest&page=2'
        response = self.client.post(reverse('task-status', args=[tasks[-1].pk]), {'complete': 'true', 'return_to': url})
        self.assertRedirects(response, url)
        response = self.client.get(url)
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(len(response.context['tasks']), 12)

    def test_external_return_urls_are_rejected(self):
        task = Task.objects.create(user=self.user, title='Safe redirect')
        for candidate in ['https://example.org/', '//example.org/', '/login/', '/\\example.org', 'http://[broken']:
            with self.subTest(candidate=candidate):
                response = self.client.post(reverse('task-status', args=[task.pk]), {'complete': 'true', 'return_to': candidate})
                self.assertRedirects(response, reverse('tasks'))

    def test_edit_preserves_list_context(self):
        task = Task.objects.create(user=self.user, title='Edit me')
        context_url = '/?status=open&search-area=Edit&sort=due'
        url = reverse('task-update', args=[task.pk])
        response = self.client.get(url, {'return_to': context_url})
        self.assertEqual(response.context['return_to'], context_url)
        response = self.client.post(url, {'title': 'Edited', 'priority': 2, 'return_to': context_url})
        self.assertRedirects(response, context_url)

    def test_export_is_private_and_contains_all_own_tasks(self):
        Task.objects.create(user=self.user, title='My task', due_date=timezone.localdate())
        Task.objects.create(user=self.other, title='Someone else')
        response = self.client.get(reverse('task-export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="daymark-tasks.json"')
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        data = response.json()
        self.assertEqual(data['version'], 2)
        self.assertEqual([task['title'] for task in data['tasks']], ['My task'])
        self.assertNotIn('user', data['tasks'][0])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('task-export')).status_code, 302)
