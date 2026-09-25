"""Task state changes shared by forms and quick actions."""
import calendar
from datetime import timedelta

from .models import Task


def schedule_next(task):
    """Called in the caller's transaction; a unique source prevents duplicate repeats."""
    if task.recurrence_created or not task.complete or not task.recurrence or not task.due_date or task.deleted_at:
        return None
    if Task.objects.filter(recurrence_source=task).exists():
        return None
    due = task.due_date
    anchor = task.recurrence_day or due.day
    if task.recurrence == 'monthly':
        year, month = (due.year + 1, 1) if due.month == 12 else (due.year, due.month + 1)
        if year > 9999:
            return None
        due = due.replace(year=year, month=month, day=min(anchor, calendar.monthrange(year, month)[1]))
    else:
        try:
            due += timedelta(days=1 if task.recurrence == 'daily' else 7)
        except OverflowError:
            return None
    task.recurrence_created = True
    task.save(update_fields=['recurrence_created'])
    following = Task.objects.create(user=task.user, title=task.title, description=task.description,
        priority=task.priority, due_date=due, project=task.project, recurrence=task.recurrence,
        recurrence_day=anchor, recurrence_source=task)
    following.tags.set(task.tags.all())
    for item in task.subtasks.all():
        following.subtasks.create(title=item.title)
    return following
