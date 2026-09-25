import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from tasks.accounts import preferences_for
from tasks.observability import PrivateErrorFormatter, ErrorWebhookHandler


class BackupTests(SimpleTestCase):
    def test_backup_and_restore_keep_rows_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, restored = [root / name for name in ['source.sqlite3', 'backup.sqlite3', 'restored.sqlite3']]
            with sqlite3.connect(source) as connection:
                connection.execute('CREATE TABLE sample (value TEXT)')
                connection.execute('INSERT INTO sample VALUES (?)', ['Preserved data'])
            databases = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': source}}
            with patch('tasks.management.commands.backup_database.settings', SimpleNamespace(DATABASES=databases)):
                call_command('backup_database', output=str(backup), stdout=StringIO())
                with self.assertRaises(CommandError):
                    call_command('backup_database', output=str(backup), stdout=StringIO())
            call_command('verify_backup', source=str(backup), output=str(restored), stdout=StringIO())
            with sqlite3.connect(restored) as connection:
                self.assertEqual(connection.execute('SELECT value FROM sample').fetchone()[0], 'Preserved data')
            with self.assertRaises(CommandError):
                call_command('verify_backup', source=str(backup), output=str(source))
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)


class ObservabilityTests(SimpleTestCase):
    def test_event_excludes_sensitive_exception_and_request_data(self):
        record = logging.LogRecord('django.request', logging.ERROR, __file__, 1,
            'secret password token task title', (), (ValueError, ValueError('private@example.test'), None))
        record.request = SimpleNamespace(method='POST', path='/reset/secret-token/', error_id='abc123', body=b'password=secret')
        record.status_code = 500
        event = json.loads(PrivateErrorFormatter().format(record))
        self.assertEqual(event, {'event': 'application_error', 'error_id': 'abc123', 'method': 'POST', 'status': 500, 'exception': 'ValueError'})

    def test_webhook_is_https_only_throttled_and_failure_safe(self):
        with self.assertRaises(ValueError):
            ErrorWebhookHandler('http://example.test')
        handler = ErrorWebhookHandler('https://example.test/events')
        record = logging.LogRecord('django', logging.ERROR, '', 0, 'private', (), None)
        with patch('tasks.observability.build_opener') as opener:
            opener.return_value.open.side_effect = OSError('Unavailable')
            handler.emit(record)
            handler.emit(record)
            self.assertEqual(opener.return_value.open.call_count, 1)
            request = opener.return_value.open.call_args.args[0]
            self.assertNotIn(b'private', request.data)


class LocaleAndPWATests(TestCase):
    def test_turkish_preference_changes_ui_and_timezone(self):
        user = get_user_model().objects.create_user('turkish')
        profile = preferences_for(user)
        profile.language, profile.timezone = 'tr', 'Europe/Istanbul'
        profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('tasks'))
        self.assertContains(response, 'Görevlerim')
        self.assertContains(response, 'lang="tr"')
        self.assertContains(self.client.get(reverse('account-settings')), 'Hesap ayarları')

    def test_anonymous_language_switch_persists(self):
        self.client.post(reverse('set_language'), {'language': 'tr', 'next': '/login/'})
        self.assertContains(self.client.get(reverse('login')), 'Giriş yap')

    def test_manifest_and_worker_are_public_and_scoped(self):
        response = self.client.get(reverse('manifest'))
        self.assertEqual(response.json()['scope'], '/')
        self.assertEqual(len(response.json()['icons']), 2)
        response = self.client.get(reverse('service-worker'))
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertContains(response, 'PUBLIC_ASSETS.includes(url.pathname)')
