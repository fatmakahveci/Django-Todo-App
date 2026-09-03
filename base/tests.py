from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Task


class TaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-password")
        self.other_user = User.objects.create_user(username="other", password="test-password")
        Task.objects.create(user=self.user, title="Write tests")
        Task.objects.create(user=self.user, title="Ship feature", complete=True)
        Task.objects.create(user=self.other_user, title="Private task")

    def test_task_string_representation(self):
        task = Task.objects.get(user=self.user, title="Write tests")
        self.assertEqual(str(task), "Write tests")

    def test_task_list_requires_login(self):
        response = self.client.get(reverse("tasks"))
        self.assertEqual(response.status_code, 302)

    def test_task_list_is_scoped_to_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Write tests")
        self.assertNotContains(response, "Private task")
        self.assertEqual(response.context["count"], 1)

    def test_task_search_filters_by_title(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tasks"), {"search-area": "ship"})

        self.assertContains(response, "Ship feature")
        self.assertNotContains(response, "Write tests")
