from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from config.security import validate_production_environment
from tasks.models import AuthAttemptBucket, Task


class ProductionValidationTests(SimpleTestCase):
    def test_rejects_weak_or_placeholder_secrets(self):
        for value in ['', 'x' * 64, 'replace-with-a-long-random-secret', 'django-insecure-' + 'abc123' * 20]:
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                validate_production_environment(value, ['example.com'])

    def test_rejects_wildcard_and_empty_hosts(self):
        secret = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789'
        for hosts in [[], ['*'], [''], ['.example.com'], ['https://example.com']]:
            with self.subTest(hosts=hosts), self.assertRaises(ImproperlyConfigured):
                validate_production_environment(secret, hosts)
        validate_production_environment(secret, ['example.com', 'localhost'])


class SecurityTests(TestCase):
    def test_login_and_admin_share_account_limit_even_with_spoofed_headers(self):
        for i in range(10):
            response = self.client.post('/login/', {'username': 'target'}, HTTP_X_FORWARDED_FOR=f'198.51.100.{i}')
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/admin/login/', {'username': 'TARGET'})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertNotIn('target', ''.join(AuthAttemptBucket.objects.values_list('key', flat=True)))

    def test_ip_limit_cannot_be_bypassed_by_changing_usernames(self):
        for i in range(40):
            response = self.client.post('/login/', {'username': f'name-{i}'}, HTTP_X_REAL_IP=f'198.51.100.{i}')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post('/login/', {'username': 'new-name'}).status_code, 429)

    def test_registration_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/register/', {}).status_code, 200)
        self.assertEqual(self.client.post('/register/', {}).status_code, 429)

    def test_counters_expire(self):
        now = timezone.now().replace(second=0, microsecond=0)
        with patch('tasks.middleware.timezone.now', return_value=now):
            for _ in range(11):
                response = self.client.post('/login/', {'username': 'target'})
            self.assertEqual(response.status_code, 429)
        with patch('tasks.middleware.timezone.now', return_value=now + timedelta(minutes=6)):
            self.assertEqual(self.client.post('/login/', {'username': 'target'}).status_code, 200)

    @override_settings(AUTH_TRUSTED_PROXIES=['127.0.0.1/32'])
    def test_explicit_proxy_configuration_separates_clients(self):
        for _ in range(5):
            self.client.post('/register/', {}, HTTP_X_REAL_IP='198.51.100.1')
        self.assertEqual(self.client.post('/register/', {}, HTTP_X_REAL_IP='198.51.100.1').status_code, 429)
        self.assertEqual(self.client.post('/register/', {}, HTTP_X_REAL_IP='198.51.100.2').status_code, 200)

    def test_csrf_rejected_requests_do_not_consume_login_budget(self):
        response = Client(enforce_csrf_checks=True).post('/login/', {'username': 'target'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AuthAttemptBucket.objects.count(), 0)

    def test_private_pages_have_no_store_and_restrictive_csp(self):
        user = get_user_model().objects.create_user('private-user')
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', response['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])

    def test_notes_are_bounded(self):
        user = get_user_model().objects.create_user('writer')
        self.client.force_login(user)
        response = self.client.post('/task-create/', {'title': 'Too much', 'priority': 2, 'description': 'x' * 10001})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors.get('description'))
        self.assertEqual(Task.objects.count(), 0)
