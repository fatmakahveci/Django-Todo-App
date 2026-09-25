from datetime import date, datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from tasks.accounts import preferences_for
from tasks.models import Task, Project, Tag, SubTask, ReminderDelivery

MAIL = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}


class PlanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('planner', email='owner@example.test', password='a-long-unique-password')
        cls.other = get_user_model().objects.create_user('other')

    def setUp(self):
        self.client.force_login(self.owner)

    def test_trash_restore_and_purge_are_scoped_and_explicit(self):
        task = Task.objects.create(user=self.owner, title='Keep me')
        self.client.post(reverse('task-delete', args=[task.pk]))
        self.assertNotContains(self.client.get(reverse('tasks')), 'Keep me')
        self.assertEqual(self.client.get(reverse('task', args=[task.pk])).status_code, 404)
        self.assertNotIn('Keep me', self.client.get(reverse('task-export')).content.decode())
        self.assertContains(self.client.get(reverse('trash')), 'Keep me')
        self.client.force_login(self.other)
        for name in ['task-restore', 'task-purge']:
            self.assertEqual(self.client.post(reverse(name, args=[task.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse('task-restore', args=[task.pk]))
        self.assertContains(self.client.get(reverse('tasks')), 'Keep me')
        self.assertEqual(self.client.post(reverse('task-purge', args=[task.pk])).status_code, 404)
        self.client.post(reverse('task-delete', args=[task.pk]))
        self.client.post(reverse('task-purge', args=[task.pk]))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_collections_cannot_be_assigned_across_accounts(self):
        project = Project.objects.create(user=self.other, name='Hidden project')
        tag = Tag.objects.create(user=self.other, name='Hidden tag')
        response = self.client.get(reverse('task-create'))
        self.assertNotContains(response, project.name)
        response = self.client.post(reverse('task-create'), {'title': 'Test', 'priority': 2, 'project': project.pk, 'tags': [tag.pk]})
        self.assertIn('project', response.context['form'].errors)
        self.assertIn('tags', response.context['form'].errors)
        self.assertFalse(Task.objects.exists())
        self.assertEqual(self.client.post(reverse('collection-delete', args=['project', project.pk])).status_code, 404)

    def test_collection_removal_preserves_tasks(self):
        project = Project.objects.create(user=self.owner, name='Work')
        task = Task.objects.create(user=self.owner, title='Plan', project=project)
        self.assertContains(self.client.get(reverse('tasks'), {'project': project.pk}), 'Plan')
        self.client.post(reverse('collection-delete', args=['project', project.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.project_id)

    def test_monthly_repeat_preserves_month_end_and_is_idempotent(self):
        task = Task.objects.create(user=self.owner, title='Month end', due_date=date(2030, 1, 31), recurrence='monthly')
        task.subtasks.create(title='Prepare', complete=True)
        url = reverse('task-status', args=[task.pk])
        self.client.post(url, {'complete': 'true'})
        self.client.post(url, {'complete': 'true'})
        self.client.post(url, {'complete': 'false'})
        self.client.post(url, {'complete': 'true'})
        self.assertEqual(Task.objects.count(), 2)
        following = Task.objects.get(recurrence_source=task)
        self.assertEqual(following.due_date, date(2030, 2, 28))
        self.assertFalse(following.subtasks.get().complete)
        self.client.post(reverse('task-status', args=[following.pk]), {'complete': 'true'})
        self.assertEqual(Task.objects.get(recurrence_source=following).due_date, date(2030, 3, 31))

    def test_edit_completion_also_schedules_and_repeat_requires_date(self):
        response = self.client.post(reverse('task-create'), {'title': 'Invalid', 'priority': 2, 'recurrence': 'daily'})
        self.assertIn('due_date', response.context['form'].errors)
        task = Task.objects.create(user=self.owner, title='Daily', due_date=date(2030, 1, 1), recurrence='daily')
        self.client.post(reverse('task-update', args=[task.pk]), {'title': task.title, 'priority': 2, 'recurrence': 'daily', 'due_date': '2030-01-01', 'complete': 'on'})
        self.assertEqual(Task.objects.get(recurrence_source=task).due_date, date(2030, 1, 2))

    def test_subtask_ownership_and_idempotent_completion(self):
        task = Task.objects.create(user=self.owner, title='Checklist')
        self.client.post(reverse('subtask-add', args=[task.pk]), {'title': 'First step'})
        item = task.subtasks.get()
        url = reverse('subtask-change', args=[item.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {'action': 'delete'}).status_code, 404)
        self.client.force_login(self.owner)
        for _ in range(2):
            self.client.post(url, {'action': 'complete'})
        item.refresh_from_db()
        self.assertTrue(item.complete)

    def test_account_email_change_requires_password_and_resets_verification(self):
        profile = preferences_for(self.owner)
        profile.email_verified = True
        profile.verified_email = self.owner.email
        profile.save()
        data = {'language': 'en', 'timezone': 'Europe/Istanbul', 'reminder_hour': 9, 'email': 'changed@example.test'}
        response = self.client.post(reverse('account-settings'), data)
        self.assertIn('current_password', response.context['form'].errors)
        data['current_password'] = 'a-long-unique-password'
        self.assertEqual(self.client.post(reverse('account-settings'), data).status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.email_verified)
        self.assertFalse(profile.reminders)

    def test_verification_is_signed_owned_and_post_only(self):
        token = signing.dumps({'user': self.owner.pk, 'email': self.owner.email}, salt='email-verification')
        url = reverse('verify-email', args=[token])
        self.client.get(url)
        self.assertFalse(preferences_for(self.owner).email_verified)
        self.client.force_login(self.other)
        self.client.post(url)
        self.assertFalse(preferences_for(self.other).email_verified)
        self.client.force_login(self.owner)
        self.client.post(url)
        self.assertTrue(preferences_for(self.owner).email_verified)

    @override_settings(MAIL_ENABLED=True, MAILERS=MAIL, PUBLIC_BASE_URL='https://todo.example.test')
    def test_reset_email_uses_canonical_origin_and_does_not_reveal_account(self):
        self.client.logout()
        for email in [self.owner.email, 'missing@example.test']:
            self.assertRedirects(self.client.post(reverse('password_reset'), {'email': email}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://todo.example.test/reset/', mail.outbox[0].body)
        self.assertNotIn('testserver', mail.outbox[0].body)

    @override_settings(MAIL_ENABLED=True, MAILERS=MAIL, PUBLIC_BASE_URL='https://todo.example.test')
    def test_reminders_require_opt_in_verification_and_local_hour(self):
        Task.objects.create(user=self.owner, title='Private task title', due_date=date(2030, 1, 2))
        profile = preferences_for(self.owner)
        profile.timezone = 'Europe/Istanbul'
        profile.reminder_hour = 8
        profile.reminders = True
        profile.save()
        now = datetime(2030, 1, 2, 6, tzinfo=dt_timezone.utc)
        with patch('tasks.management.commands.send_reminders.timezone.now', return_value=now):
            call_command('send_reminders', send=True, stdout=StringIO())
            self.assertEqual(len(mail.outbox), 0)
            profile.email_verified = True
            profile.verified_email = self.owner.email
            profile.save()
            call_command('send_reminders', stdout=StringIO())
            self.assertFalse(ReminderDelivery.objects.exists())
            call_command('send_reminders', send=True, stdout=StringIO())
            call_command('send_reminders', send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('Private task title', mail.outbox[0].body)
        self.assertIsNotNone(ReminderDelivery.objects.get().sent_at)

    def test_account_pages_render(self):
        for name in ['account-settings', 'password_change', 'password_reset', 'collections', 'trash']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    @override_settings(MAIL_ENABLED=True, MAILERS=MAIL)
    def test_verification_cannot_follow_a_changed_email_address(self):
        profile = preferences_for(self.owner)
        profile.email_verified = True
        profile.verified_email = self.owner.email
        profile.reminders = True
        profile.reminder_hour = 0
        profile.save()
        self.owner.email = 'different@example.test'
        self.owner.save(update_fields=['email'])
        Task.objects.create(user=self.owner, title='Private', due_date=date(2000, 1, 1))
        call_command('send_reminders', send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReminderDelivery.objects.exists())

    def test_purging_next_occurrence_does_not_recreate_it_on_retry(self):
        task = Task.objects.create(user=self.owner, title='Weekly', due_date=date(2030, 1, 1), recurrence='weekly')
        url = reverse('task-status', args=[task.pk])
        self.client.post(url, {'complete': 'true'})
        following = Task.objects.get(recurrence_source=task)
        self.client.post(reverse('task-delete', args=[following.pk]))
        self.client.post(reverse('task-purge', args=[following.pk]))
        self.client.post(url, {'complete': 'true'})
        self.assertEqual(Task.objects.count(), 1)

    def test_today_filter_respects_user_timezone_across_midnight(self):
        profile = preferences_for(self.owner)
        profile.timezone = 'Europe/Istanbul'
        profile.save()
        local_today = Task.objects.create(user=self.owner, title='Local today', due_date=date(2030, 1, 3))
        Task.objects.create(user=self.owner, title='UTC today', due_date=date(2030, 1, 2))
        with patch('django.utils.timezone.now', return_value=datetime(2030, 1, 2, 23, tzinfo=dt_timezone.utc)):
            self.client.force_login(self.owner)
            response = self.client.get(reverse('tasks'), {'status': 'today'})
        self.assertEqual(list(response.context['tasks']), [local_today])


    def test_postponing_resets_monthly_anchor_only_when_date_changes(self):
        from django.utils import timezone
        from datetime import timedelta
        tomorrow = timezone.localdate() + timedelta(days=1)
        task = Task.objects.create(user=self.owner, title='Monthly', recurrence='monthly', recurrence_day=31, due_date=tomorrow)
        url = reverse('task-postpone', args=[task.pk])
        self.client.post(url, {'days': '1'})
        task.refresh_from_db()
        self.assertEqual(task.recurrence_day, 31)
        self.client.post(url, {'days': '7'})
        task.refresh_from_db()
        self.assertIsNone(task.recurrence_day)
