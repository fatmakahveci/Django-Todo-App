from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from tasks.models import AuthAttemptBucket


class SecurityRegressionTests(TestCase):
    def test_admin_password_change_shares_account_password_budget(self):
        user = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(user)
        for index in range(10):
            response = self.client.post('/admin/password_change/',
                {'old_password': 'wrong'}, REMOTE_ADDR=f'198.51.100.{index}')
            self.assertEqual(response.status_code, 200)
        for path in ['/admin/password_change/', '/account/password/', '/account/']:
            with self.subTest(path=path):
                response = self.client.post(path, {'old_password': 'wrong'},
                    REMOTE_ADDR='203.0.113.1')
                self.assertEqual(response.status_code, 429)

    def test_registration_passwords_are_redacted_from_error_reports(self):
        response = self.client.post('/register/', {
            'password1': 'secret-value', 'password2': 'secret-value',
        })
        from django.views.debug import SafeExceptionReporterFilter
        with self.settings(DEBUG=False):
            data = SafeExceptionReporterFilter().get_post_parameters(response.wsgi_request)
        self.assertEqual(data['password1'], '********************')
        self.assertEqual(data['password2'], '********************')

    def test_oversized_multipart_is_rejected_before_csrf_or_upload_parsing(self):
        for client in [self.client, Client(enforce_csrf_checks=True)]:
            with self.subTest(csrf=client.handler.enforce_csrf_checks):
                with patch('django.http.multipartparser.MultiPartParser.parse') as parse:
                    response = client.post('/register/', {
                        'payload': SimpleUploadedFile('large.bin', b'x' * 65537),
                    })
                self.assertEqual(response.status_code, 413)
                parse.assert_not_called()
        self.assertFalse(AuthAttemptBucket.objects.exists())

    def test_small_registration_form_still_works(self):
        response = self.client.post('/register/', {})
        self.assertEqual(response.status_code, 200)
