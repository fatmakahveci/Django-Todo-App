from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "priority", "due_date", "complete"]
    list_filter = ["complete", "priority", "due_date"]
    search_fields = ["title", "description", "user__username"]
    list_select_related = ["user"]
