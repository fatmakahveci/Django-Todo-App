"""Todo project URL configuration."""
from django.contrib import admin
from django.urls import include, path
from .health import health

urlpatterns = [
    path('healthz/', health, name='health'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('', include('tasks.urls')),
]

handler500 = 'config.errors.server_error'
