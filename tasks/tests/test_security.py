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


class AccountAbuseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('account-owner', email='owner@example.test')

    def setUp(self):
        self.client.force_login(self.user)

    def test_password_checks_share_a_user_budget_across_ips_and_routes(self):
        for index in range(10):
            path = '/account/' if index % 2 else '/account/password/'
            response = self.client.post(path, {
                'email': 'changed@example.test', 'current_password': 'wrong',
                'old_password': 'wrong', 'language': 'en', 'timezone': 'UTC', 'reminder_hour': 8,
            }, REMOTE_ADDR=f'198.51.100.{index}')
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/account/password/', {'old_password': 'wrong'}, REMOTE_ADDR='203.0.113.1')
        self.assertEqual(response.status_code, 429)

    def test_reset_recipient_budget_cannot_be_bypassed_by_rotating_ips(self):
        self.client.logout()
        for index in range(5):
            self.assertEqual(self.client.post('/password-reset/', {'email': 'Owner@example.test'},
                REMOTE_ADDR=f'198.51.100.{index}').status_code, 200)
        response = self.client.post('/password-reset/', {'email': 'owner@EXAMPLE.TEST'}, REMOTE_ADDR='203.0.113.1')
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('owner', ''.join(AuthAttemptBucket.objects.values_list('key', flat=True)))

    def test_verification_mail_is_limited_per_account_across_ips(self):
        for index in range(5):
            self.assertEqual(self.client.post('/account/verify/send/', REMOTE_ADDR=f'198.51.100.{index}').status_code, 302)
        self.assertEqual(self.client.post('/account/verify/send/', REMOTE_ADDR='203.0.113.1').status_code, 429)


    def test_reset_and_verification_share_recipient_budget(self):
        for index in range(5):
            self.client.post('/account/verify/send/', REMOTE_ADDR=f'198.51.100.{index}')
        self.client.logout()
        self.assertEqual(self.client.post('/password-reset/', {'email': self.user.email},
            REMOTE_ADDR='203.0.113.1').status_code, 429)

    def test_account_password_is_marked_sensitive_for_error_reports(self):
        response = self.client.post('/account/', {'current_password': 'private-value'})
        self.assertIn('current_password', response.wsgi_request.sensitive_post_parameters)

    def test_private_links_are_not_sent_as_referrers(self):
        self.assertEqual(self.client.get('/account/')['Referrer-Policy'], 'no-referrer')
