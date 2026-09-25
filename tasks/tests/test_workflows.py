from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("owner", password="a-long-test-password")
        cls.other = get_user_model().objects.create_user("other", password="a-long-test-password")
        cls.task = Task.objects.create(user=cls.owner, title="Private plan", description="Keep this private")

    def setUp(self):
        self.client.force_login(self.owner)

    def test_other_users_cannot_read_or_change_tasks(self):
        self.client.force_login(self.other)
        for route in ["task", "task-update", "task-delete"]:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route, args=[self.task.pk])).status_code, 404)
        for route in ["task-update", "task-delete", "task-status"]:
            with self.subTest(route=route):
                self.assertEqual(self.client.post(reverse(route, args=[self.task.pk]), {
                    "title": "Stolen", "priority": 1, "complete": "true"
                }).status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Private plan")
        self.assertFalse(self.task.complete)

    def test_anonymous_detail_redirects_to_absolute_login_route(self):
        self.client.logout()
        url = reverse("task", args=[self.task.pk])
        self.assertRedirects(self.client.get(url), f"/login/?next={url}")

    def test_owner_can_create_update_and_delete(self):
        response = self.client.post(reverse("task-create"), {
            "title": "  New plan  ", "priority": 1, "due_date": "2030-01-15", "user": self.other.pk,
        })
        self.assertRedirects(response, reverse("tasks"))
        task = Task.objects.get(title="New plan")
        self.assertEqual(task.user, self.owner)
        self.assertEqual(task.priority, 1)
        self.assertEqual(str(task.due_date), "2030-01-15")
        response = self.client.post(reverse("task-update", args=[task.pk]), {
            "title": "Updated", "priority": 3, "complete": "on", "user": self.other.pk,
        })
        self.assertRedirects(response, reverse("tasks"))
        task.refresh_from_db()
        self.assertEqual(task.user, self.owner)
        self.assertTrue(task.complete)
        self.assertEqual(task.title, "Updated")
        self.assertRedirects(self.client.post(reverse("task-delete", args=[task.pk])), reverse("tasks"))
        self.assertTrue(Task.objects.filter(pk=task.pk, deleted_at__isnull=False).exists())

    def test_blank_title_and_invalid_priority_are_rejected(self):
        for data in [{"title": "   ", "priority": 2}, {"title": "Invalid", "priority": 9}]:
            with self.subTest(data=data):
                response = self.client.post(reverse("task-create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(Task.objects.count(), 1)

    def test_completion_is_post_only_and_idempotent(self):
        url = reverse("task-status", args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {"complete": "maybe"}).status_code, 400)
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {"complete": "true"}), reverse("tasks"))
        self.task.refresh_from_db()
        self.assertTrue(self.task.complete)
        self.client.post(url, {"complete": "false"})
        self.task.refresh_from_db()
        self.assertFalse(self.task.complete)

    def test_status_change_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("task-status", args=[self.task.pk]), {"complete": "true"}).status_code, 403)

    def test_logout_requires_post_and_ends_session(self):
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_search_cannot_inject_html_attributes(self):
        class InputParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "input" and attrs.get("name") == "search-area":
                    self.search = attrs
        payload = 'x autofocus onfocus=alert(1) " <script>'
        response = self.client.get(reverse("tasks"), {"search-area": payload})
        parser = InputParser()
        parser.feed(response.content.decode())
        self.assertEqual(parser.search["value"], payload)
        self.assertNotIn("onfocus", parser.search)
        self.assertNotIn("autofocus", parser.search)

    def test_description_search_and_overdue_filter(self):
        overdue = Task.objects.create(user=self.owner, title="Due", description="needle", due_date=timezone.localdate() - timedelta(days=1))
        Task.objects.create(user=self.owner, title="Done", complete=True, due_date=overdue.due_date)
        Task.objects.create(user=self.other, title="Hidden", due_date=overdue.due_date)
        response = self.client.get(reverse("tasks"), {"status": "overdue", "search-area": "needle"})
        self.assertEqual(list(response.context["tasks"]), [overdue])
        self.assertEqual(response.context["stats"]["total"], 3)
        self.assertEqual(response.context["stats"]["overdue"], 1)
        self.assertTrue(overdue.is_overdue)
        overdue.complete = True
        self.assertFalse(overdue.is_overdue)

    def test_pagination_and_full_queryset_are_user_scoped(self):
        Task.objects.bulk_create([Task(user=self.owner, title=f"Plan {i}") for i in range(15)])
        Task.objects.create(user=self.other, title="Secret")
        response = self.client.get(reverse("tasks"), {"status": "open", "search-area": "Plan"})
        self.assertEqual(len(response.context["tasks"]), 12)
        self.assertEqual(response.context["paginator"].count, 16)
        self.assertTrue(all(task.user_id == self.owner.pk for task in response.context["object_list"]))
        self.assertContains(response, "page=2")
        response = self.client.get(reverse("tasks"), {"status": "open", "search-area": "Plan", "page": 2})
        self.assertEqual(len(response.context["tasks"]), 4)

    def test_login_honors_safe_next_and_rejects_external_next(self):
        self.client.logout()
        url = reverse("task", args=[self.task.pk])
        response = self.client.post(reverse("login"), {"username": "owner", "password": "a-long-test-password", "next": url})
        self.assertRedirects(response, url)
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "owner", "password": "a-long-test-password", "next": "https://example.org/"})
        self.assertRedirects(response, reverse("tasks"))

    def test_authenticated_user_cannot_register_another_account(self):
        response = self.client.post(reverse("register"), {"username": "unexpected"})
        self.assertRedirects(response, reverse("tasks"))
        self.assertFalse(get_user_model().objects.filter(username="unexpected").exists())

    def test_registration_creates_session(self):
        self.client.logout()
        response = self.client.post(reverse("register"), {"username": "new-person", "email": "new@example.test", "password1": "a-unique-passphrase-852", "password2": "a-unique-passphrase-852"})
        self.assertRedirects(response, reverse("tasks"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_health_endpoint_is_public_and_checks_database(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})
        self.assertEqual(self.client.post(reverse("health")).status_code, 405)
        with patch("config.health.Task.objects.order_by", side_effect=DatabaseError("private details")):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "private details", status_code=503)

    def test_all_task_pages_render(self):
        for route, args in [("tasks", []), ("task-create", []), ("task", [self.task.pk]),
                            ("task-update", [self.task.pk]), ("task-delete", [self.task.pk])]:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "/static/tasks/app.css")
                self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_completed_and_open_filters(self):
        done = Task.objects.create(user=self.owner, title="Done", complete=True)
        response = self.client.get(reverse("tasks"), {"status": "completed"})
        self.assertEqual(list(response.context["tasks"]), [done])
        response = self.client.get(reverse("tasks"), {"status": "open"})
        self.assertEqual(list(response.context["tasks"]), [self.task])

    def test_task_title_and_notes_are_escaped(self):
        self.task.title = '<script>alert("title")</script>'
        self.task.description = '<img src=x onerror=alert(1)>'
        self.task.save()
        response = self.client.get(reverse("task", args=[self.task.pk]))
        self.assertNotContains(response, "<script>")
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;img")
