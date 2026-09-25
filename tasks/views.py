import csv
import json
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, F, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from .forms import QuickTaskForm, TaskForm
from .models import Task


def list_return_url(request):
    """Accept only this app's list path; never redirect to a submitted external URL."""
    candidate = request.POST.get("return_to", request.GET.get("return_to", ""))
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return reverse("tasks")
    if parts.scheme or parts.netloc or parts.path != reverse("tasks") or len(candidate) > 2048:
        return reverse("tasks")
    return reverse("tasks") + (f"?{parts.query}" if parts.query else "")


class CustomLoginView(LoginView):
    template_name = "tasks/auth_login.html"
    redirect_authenticated_user = True
    # Django validates the optional next URL to prevent off-site redirects.
    next_page = reverse_lazy("tasks")


class RegisterPage(FormView):
    template_name = "tasks/auth_register.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("tasks")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tasks")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.save())
        messages.success(self.request, "Welcome! Make room for what matters.")
        return super().form_valid(form)


class OwnedTaskMixin(LoginRequiredMixin):
    model = Task

    def get_queryset(self):
        # Enforce ownership before resolving any task ID, including write requests.
        return super().get_queryset().filter(user=self.request.user)


class TaskList(OwnedTaskMixin, ListView):
    context_object_name = "tasks"
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset()
        self.search_input = self.request.GET.get("search-area", "").strip()[:200]
        self.status = self.request.GET.get("status", "all")
        if self.status not in {"all", "open", "completed", "overdue", "today", "upcoming", "undated"}:
            self.status = "all"
        if self.search_input:
            queryset = queryset.filter(Q(title__icontains=self.search_input) | Q(description__icontains=self.search_input))
        if self.status == "open":
            queryset = queryset.filter(complete=False)
        elif self.status == "completed":
            queryset = queryset.filter(complete=True)
        elif self.status == "overdue":
            queryset = queryset.filter(complete=False, due_date__lt=timezone.localdate())
        elif self.status == "today":
            queryset = queryset.filter(complete=False, due_date=timezone.localdate())
        elif self.status == "upcoming":
            today = timezone.localdate()
            queryset = queryset.filter(complete=False, due_date__gt=today, due_date__lte=today + timedelta(days=7))
        elif self.status == "undated":
            queryset = queryset.filter(complete=False, due_date__isnull=True)
        self.priority = self.request.GET.get("priority", "")
        if self.priority in {"1", "2", "3"}:
            queryset = queryset.filter(priority=int(self.priority))
        else:
            self.priority = ""
        self.sort = self.request.GET.get("sort", "priority")
        orders = {
            "priority": ["complete", "priority", "-create", "-pk"],
            "due": ["complete", F("due_date").asc(nulls_last=True), "priority", "-pk"],
            "newest": ["-create", "-pk"],
            "oldest": ["create", "pk"],
        }
        if self.sort not in orders:
            self.sort = "priority"
        return queryset.order_by(*orders[self.sort])

    def get_paginate_by(self, queryset):
        value = self.request.GET.get("per_page", "12")
        return int(value) if value in {"12", "24", "48"} else 12

    def paginate_queryset(self, queryset, page_size):
        # Completing the last item on a filtered page must not lead to a 404.
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get("page", 1))
        return paginator, page, page.object_list, page.has_other_pages()

    def post(self, request, *args, **kwargs):
        self.quick_form = QuickTaskForm(request.POST)
        if self.quick_form.is_valid():
            task = self.quick_form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, "Task added. Add another whenever you're ready.")
            return redirect("tasks")
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(), status=400)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Dashboard totals describe all owned tasks, independently of the current filter.
        stats = Task.objects.filter(user=self.request.user).aggregate(
            total=Count("pk"),
            completed=Count("pk", filter=Q(complete=True)),
            overdue=Count("pk", filter=Q(complete=False, due_date__lt=timezone.localdate())),
        )
        stats["open"] = stats["total"] - stats["completed"]
        stats["progress"] = round(stats["completed"] * 100 / stats["total"]) if stats["total"] else 0
        context.update(
            stats=stats, count=stats["open"], search_input=self.search_input,
            status=self.status, sort=self.sort, priority=self.priority,
            per_page=self.get_paginate_by(self.object_list),
            quick_form=getattr(self, "quick_form", QuickTaskForm()),
        )
        return context


class TaskDetail(OwnedTaskMixin, DetailView):
    context_object_name = "task"


class TaskCreate(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Task
    form_class = TaskForm
    success_url = reverse_lazy("tasks")
    success_message = "Task added. One step closer."

    def form_valid(self, form):
        # Ownership always comes from the session, never from submitted form data.
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.POST.get("add_another") == "true":
            return reverse("task-create")
        return super().get_success_url()


class TaskUpdate(OwnedTaskMixin, SuccessMessageMixin, UpdateView):
    form_class = TaskForm
    success_url = reverse_lazy("tasks")
    success_message = "Task updated."

    def get_success_url(self):
        return list_return_url(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["return_to"] = list_return_url(self.request)
        return context


class TaskDelete(OwnedTaskMixin, SuccessMessageMixin, DeleteView):
    context_object_name = "task"
    success_url = reverse_lazy("tasks")
    success_message = "Task deleted."


class TaskStatus(OwnedTaskMixin, View):
    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)

    def post(self, request, pk):
        task = get_object_or_404(self.get_queryset(), pk=pk)
        value = request.POST.get("complete")
        if value not in {"true", "false"}:
            return HttpResponseBadRequest("Expected complete=true or complete=false.")
        # Assign the requested state rather than toggling: retrying a POST is safe.
        task.complete = value == "true"
        task.save(update_fields=["complete"])
        messages.success(request, "Task completed." if task.complete else "Task reopened.")
        return redirect(list_return_url(request))


class TaskExport(LoginRequiredMixin, View):
    def get(self, request):
        tasks = list(Task.objects.filter(user=request.user).values(
            "title", "description", "priority", "due_date", "complete", "create"
        ))
        response = HttpResponse(
            json.dumps({"format": "daymark-tasks", "version": 1, "tasks": tasks},
                       cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="daymark-tasks.json"'
        response["Cache-Control"] = "private, no-store"
        return response


class TaskDuplicate(LoginRequiredMixin, View):
    def post(self, request, pk):
        original = get_object_or_404(Task, pk=pk, user=request.user)
        copy = Task.objects.create(
            user=request.user, title=f"{original.title[:193]} (copy)",
            description=original.description, priority=original.priority,
            due_date=original.due_date, complete=False,
        )
        messages.success(request, "Task copied. Adjust the details for a fresh start.")
        return redirect("task-update", pk=copy.pk)


class TaskPostpone(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk, user=request.user)
        days = request.POST.get("days")
        if days not in {"1", "7"} or task.complete:
            return HttpResponseBadRequest("Choose tomorrow or next week for an open task.")
        # These are absolute targets relative to today; retries don't add more days.
        target = timezone.localdate() + timedelta(days=int(days))
        if task.due_date and task.due_date > target:
            messages.info(request, "This task is already scheduled later; its date was kept.")
        else:
            task.due_date = target
            task.save(update_fields=["due_date"])
            messages.success(request, "Due date updated.")
        return redirect("task", pk=task.pk)


def csv_cell(value):
    text = str(value or "")
    # Neutralize formula-like text even if prefixed with whitespace/control characters.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


class TaskCSVExport(LoginRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="daymark-tasks.csv"'
        response["Cache-Control"] = "private, no-store"
        response.write("\ufeff")  # Let spreadsheet applications detect UTF-8 correctly.
        writer = csv.writer(response)
        writer.writerow(["Title", "Notes", "Priority", "Due date", "Completed", "Created"])
        for task in Task.objects.filter(user=request.user).iterator():
            writer.writerow([csv_cell(task.title), csv_cell(task.description),
                             task.get_priority_display(), task.due_date or "",
                             "Yes" if task.complete else "No", task.create.isoformat()])
        return response
