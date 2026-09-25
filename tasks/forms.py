from django.utils.translation import gettext_lazy as _
from django import forms

from .models import Task, Project, Tag


class TaskForm(forms.ModelForm):
    description = forms.CharField(label=_("Notes"), required=False, max_length=10000, widget=forms.Textarea(attrs={"rows": 5, "placeholder": _("Add a little context…")}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Never expose another account's collections in choices or accept their IDs.
        self.fields['project'].queryset = Project.objects.filter(user=user) if user else Project.objects.none()
        self.fields['tags'].queryset = Tag.objects.filter(user=user) if user else Tag.objects.none()
        self.fields['tags'].help_text = _('Hold Ctrl or Command to select several tags. Manage tags under Projects & tags.')
        self.fields['recurrence'].help_text = _('Completing this task creates the next occurrence. A due date is required.')

    def clean(self):
        data = super().clean()
        if data.get('recurrence') and not data.get('due_date'):
            self.add_error('due_date', _('Choose a due date for a repeating task.'))
        return data

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date", "project", "tags", "recurrence", "complete"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": _("What needs to get done?"), "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": _("Add a little context…")}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"title": _("Title"), "description": _("Notes"), "priority": _("Priority"), "project": _("Project"), "tags": _("Tags"), "recurrence": _("Repeat"), "complete": _("Mark as completed"), "due_date": _("Due date")}


class QuickTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "due_date"]
        widgets = {"title": forms.TextInput(attrs={
            "placeholder": _("Add a task and press Enter…"),
            "id": "quick-title",
            "autocomplete": "off",
        }), "due_date": forms.DateInput(attrs={"type": "date", "id": "quick-due"})}
