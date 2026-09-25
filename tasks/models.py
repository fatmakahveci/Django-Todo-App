from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Priority(models.IntegerChoices):
        HIGH = 1, "High"
        NORMAL = 2, "Normal"
        LOW = 3, "Low"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    complete = models.BooleanField(default=False)
    create = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and not self.complete)

    def __str__(self):
        return self.title

    class Meta:
        # The final primary-key sort makes pagination deterministic when timestamps match.
        ordering = ["complete", "priority", "-create", "-pk"]
        indexes = [models.Index(fields=["user", "complete"], name="task_user_complete_idx")]


class AuthAttemptBucket(models.Model):
    """Shared, short-lived counters; no raw usernames or IP addresses are stored."""

    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
