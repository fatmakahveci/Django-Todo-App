from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from tasks.models import Task


@require_GET
def health(request):
    try:
        # Probe the application table and new columns, not merely the DB connection.
        list(Task.objects.order_by().values_list("priority", "due_date")[:1])
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
