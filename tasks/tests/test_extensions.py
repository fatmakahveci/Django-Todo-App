import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task


class ExtensionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('extension-owner')
        cls.other = get_user_model().objects.create_user('extension-other')

    def setUp(self):
        self.client.force_login(self.user)
        self.task = Task.objects.create(user=self.user, title='Original', description='Notes', priority=1)

    def test_quick_add_date_and_validation(self):
        self.assertEqual(self.client.post('/', {'title': 'Scheduled', 'due_date': '2030-05-04'}).status_code, 302)
        self.assertEqual(str(Task.objects.get(title='Scheduled').due_date), '2030-05-04')
        response = self.client.post('/', {'title': 'Invalid date', 'due_date': 'not-a-date'})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['quick_form'].errors.get('due_date'))
        self.assertFalse(Task.objects.filter(title='Invalid date').exists())

    def test_priority_and_undated_filters_combine(self):
        Task.objects.create(user=self.user, title='Dated', priority=1, due_date=timezone.localdate())
        Task.objects.create(user=self.user, title='Low', priority=3)
        Task.objects.create(user=self.other, title='Private', priority=1)
        response = self.client.get('/', {'priority': '1', 'status': 'undated'})
        self.assertEqual(list(response.context['tasks']), [self.task])
        self.assertEqual(self.client.get('/', {'priority': 'invalid'}).context['priority'], '')

    def test_page_size_is_bounded(self):
        Task.objects.bulk_create([Task(user=self.user, title=f'Item {i}') for i in range(50)])
        for size in [12, 24, 48]:
            self.assertEqual(len(self.client.get('/', {'per_page': size}).context['tasks']), size)
        self.assertEqual(len(self.client.get('/', {'per_page': '1000000'}).context['tasks']), 12)

    def test_duplicate_copies_details_but_reopens_and_preserves_original(self):
        self.task.complete = True
        self.task.due_date = timezone.localdate()
        self.task.save()
        response = self.client.post(reverse('task-duplicate', args=[self.task.pk]))
        copied = Task.objects.exclude(pk=self.task.pk).get()
        self.assertRedirects(response, reverse('task-update', args=[copied.pk]))
        self.assertEqual(copied.title, 'Original (copy)')
        self.assertEqual(copied.description, 'Notes')
        self.assertEqual(copied.priority, 1)
        self.assertEqual(copied.due_date, self.task.due_date)
        self.assertEqual(copied.user, self.user)
        self.assertFalse(copied.complete)
        self.task.refresh_from_db()
        self.assertTrue(self.task.complete)

    def test_new_actions_are_owned_post_only_and_csrf_protected(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for route in ['task-duplicate', 'task-postpone']:
            url = reverse(route, args=[self.task.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(strict.post(url, {'days': '1'}).status_code, 403)
            self.client.force_login(self.other)
            self.assertEqual(self.client.post(url, {'days': '1'}).status_code, 404)
            self.client.force_login(self.user)

    def test_postpone_is_repeatable_and_never_moves_a_later_date_back(self):
        url = reverse('task-postpone', args=[self.task.pk])
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {'days': '1'}), reverse('task', args=[self.task.pk]))
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date, timezone.localdate() + timedelta(days=1))
        self.client.post(url, {'days': '7'})
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date, timezone.localdate() + timedelta(days=7))
        self.client.post(url, {'days': '1'})
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date, timezone.localdate() + timedelta(days=7))
        self.assertEqual(self.client.post(url, {'days': '-1'}).status_code, 400)
        self.task.complete = True
        self.task.save()
        self.assertEqual(self.client.post(url, {'days': '7'}).status_code, 400)

    def test_csv_export_escapes_formulas_and_is_private(self):
        self.task.title = '=1+1'
        self.task.description = '  @SUM(1,2)\nNotes, with commas'
        self.task.save()
        Task.objects.create(user=self.other, title='Private')
        response = self.client.get(reverse('task-export-csv'))
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "'=1+1")
        self.assertEqual(rows[1][1], "'  @SUM(1,2)\nNotes, with commas")
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('task-export-csv')).status_code, 302)

    def test_save_and_add_another(self):
        response = self.client.post(reverse('task-create'), {'title': 'Next item', 'priority': 2, 'add_another': 'true'})
        self.assertRedirects(response, reverse('task-create'))
        self.assertTrue(Task.objects.filter(user=self.user, title='Next item').exists())

    def test_expanded_notes_are_escaped_and_not_truncated(self):
        self.task.description = 'Notes ' * 40 + '<script>alert(1)</script>'
        self.task.save()
        response = self.client.get('/')
        self.assertContains(response, '<details class="task-notes">')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'Keyboard shortcuts')
