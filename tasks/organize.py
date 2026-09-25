from django.utils.translation import gettext_lazy as _
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView, DeleteView
from django.urls import reverse_lazy

from .models import Task, Project, Tag, SubTask


class Trash(LoginRequiredMixin, ListView):
    template_name = 'tasks/trash.html'
    context_object_name = 'tasks'
    paginate_by = 24

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user, deleted_at__isnull=False).order_by('-deleted_at', '-pk')


class RestoreTask(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk, user=request.user, deleted_at__isnull=False)
        task.deleted_at = None
        task.save(update_fields=['deleted_at'])
        messages.success(request, _('Task restored.'))
        return redirect('trash')


class PurgeTask(LoginRequiredMixin, DeleteView):
    template_name = 'tasks/purge_task.html'
    success_url = reverse_lazy('trash')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user, deleted_at__isnull=False)


class CollectionForm(forms.Form):
    kind = forms.ChoiceField(label=_("Type"), choices=[('project', _('Project')), ('tag', _('Tag'))])
    name = forms.CharField(max_length=80, label=_("Name"))

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.cleaned_data.get('kind') == 'tag' and len(name) > 40:
            raise forms.ValidationError(_('Tag names can have at most 40 characters.'))
        return name


class Collections(LoginRequiredMixin, View):
    def get(self, request):
        return self.render(request, CollectionForm())

    def render(self, request, form):
        return render(request, 'tasks/collections.html', {'form': form,
            'projects': Project.objects.filter(user=request.user), 'tags': Tag.objects.filter(user=request.user)})

    def post(self, request):
        form = CollectionForm(request.POST)
        if form.is_valid():
            model = Project if form.cleaned_data['kind'] == 'project' else Tag
            model.objects.get_or_create(user=request.user, name=form.cleaned_data['name'])
            messages.success(request, _('Collection saved.'))
            return redirect('collections')
        return self.render(request, form)


class DeleteCollection(LoginRequiredMixin, DeleteView):
    template_name = 'tasks/delete_collection.html'
    success_url = reverse_lazy('collections')

    def get_queryset(self):
        if self.kwargs['kind'] not in {'project', 'tag'}:
            from django.http import Http404
            raise Http404
        model = Project if self.kwargs['kind'] == 'project' else Tag
        return model.objects.filter(user=self.request.user)


class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ['title']


class AddSubTask(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk, user=request.user, deleted_at__isnull=True)
        form = SubTaskForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.task = task
            item.save()
        else:
            messages.error(request, _('Enter a subtask title of 1–200 characters.'))
        return redirect('task', pk=task.pk)


class ChangeSubTask(LoginRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(SubTask, pk=pk, task__user=request.user, task__deleted_at__isnull=True)
        task_id = item.task_id
        action = request.POST.get('action')
        if action == 'delete':
            item.delete()
        elif action in {'complete', 'reopen'}:
            item.complete = action == 'complete'
            item.save(update_fields=['complete'])
        else:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest('Invalid subtask action.')
        return redirect('task', pk=task_id)
