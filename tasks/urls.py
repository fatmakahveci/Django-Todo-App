from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("tasks/export.csv", views.TaskCSVExport.as_view(), name="task-export-csv"),
    path("task/<int:pk>/duplicate/", views.TaskDuplicate.as_view(), name="task-duplicate"),
    path("task/<int:pk>/postpone/", views.TaskPostpone.as_view(), name="task-postpone"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("register/", views.RegisterPage.as_view(), name="register"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("tasks/export/", views.TaskExport.as_view(), name="task-export"),
    path("", views.TaskList.as_view(), name="tasks"),
    path("task/<int:pk>/", views.TaskDetail.as_view(), name="task"),
    path("task-create/", views.TaskCreate.as_view(), name="task-create"),
    path("task-update/<int:pk>/", views.TaskUpdate.as_view(), name="task-update"),
    path("task-delete/<int:pk>/", views.TaskDelete.as_view(), name="task-delete"),
    path("task/<int:pk>/status/", views.TaskStatus.as_view(), name="task-status"),
]
