from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models
from django.utils import timezone


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [models.UniqueConstraint(fields=['user', 'name'], name='project_owner_name')]

    def __str__(self):
        return self.name


class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [models.UniqueConstraint(fields=['user', 'name'], name='tag_owner_name')]

    def __str__(self):
        return self.name


class Task(models.Model):
    class Priority(models.IntegerChoices):
        HIGH = 1, _("High")
        NORMAL = 2, _("Normal")
        LOW = 3, _("Low")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    complete = models.BooleanField(default=False)
    create = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag, blank=True)
    recurrence = models.CharField(max_length=10, blank=True, default='', choices=[('', _('Never')), ('daily', _('Daily')), ('weekly', _('Weekly')), ('monthly', _('Monthly'))])
    recurrence_created = models.BooleanField(default=False, editable=False)
    recurrence_day = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    recurrence_source = models.OneToOneField('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='next_occurrence', editable=False)

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


class UserPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences')
    language = models.CharField(max_length=2, choices=[('en', 'English'), ('tr', 'Türkçe')], default='en')
    timezone = models.CharField(max_length=64, default='UTC')
    email_verified = models.BooleanField(default=False)
    verified_email = models.EmailField(blank=True, default="", editable=False)
    reminders = models.BooleanField(default=False)
    reminder_hour = models.PositiveSmallIntegerField(default=8)

    @property
    def email_is_verified(self):
        # Bind verification to the address itself, including concurrent account changes.
        return bool(self.email_verified and self.verified_email and self.verified_email == self.user.email)


class SubTask(models.Model):
    task = models.ForeignKey(Task, related_name='subtasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    complete = models.BooleanField(default=False)

    class Meta:
        ordering = ['pk']


class ReminderDelivery(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField()
    sent_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'day'], name='reminder_user_day')]
