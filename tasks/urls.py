from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views, accounts, organize, pwa
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('manifest.webmanifest', pwa.manifest, name='manifest'),
    path('service-worker.js', pwa.service_worker, name='service-worker'),
    path('trash/', organize.Trash.as_view(), name='trash'),
    path('trash/<int:pk>/restore/', organize.RestoreTask.as_view(), name='task-restore'),
    path('trash/<int:pk>/delete/', organize.PurgeTask.as_view(), name='task-purge'),
    path('collections/', organize.Collections.as_view(), name='collections'),
    path('collections/<str:kind>/<int:pk>/delete/', organize.DeleteCollection.as_view(), name='collection-delete'),
    path('task/<int:pk>/subtasks/', organize.AddSubTask.as_view(), name='subtask-add'),
    path('subtask/<int:pk>/', organize.ChangeSubTask.as_view(), name='subtask-change'),
    path('account/', accounts.AccountSettings.as_view(), name='account-settings'),
    path('account/verify/send/', accounts.SendVerification.as_view(), name='send-verification'),
    path('account/verify/<str:token>/', accounts.VerifyEmail.as_view(), name='verify-email'),
    path('account/password/', auth_views.PasswordChangeView.as_view(template_name='tasks/password_change_form.html'), name='password_change'),
    path('account/password/done/', auth_views.PasswordChangeDoneView.as_view(template_name='tasks/password_change_done.html'), name='password_change_done'),
    path('password-reset/', accounts.AccountPasswordReset.as_view(), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(template_name='tasks/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='tasks/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='tasks/password_reset_complete.html'), name='password_reset_complete'),
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
