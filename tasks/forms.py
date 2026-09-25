from django import forms

from .models import Task


class TaskForm(forms.ModelForm):
    description = forms.CharField(required=False, max_length=10000, widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Add a little context…"}))

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date", "complete"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "What needs to get done?", "autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Add a little context…"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"complete": "Mark as completed", "due_date": "Due date"}


class QuickTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "due_date"]
        widgets = {"title": forms.TextInput(attrs={
            "placeholder": "Add a task and press Enter…",
            "id": "quick-title",
            "autocomplete": "off",
        }), "due_date": forms.DateInput(attrs={"type": "date", "id": "quick-due"})}
