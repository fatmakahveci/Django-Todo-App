"""Container settings for deployment behind a trusted HTTPS reverse proxy."""

import os

from .settings import *  # noqa: F403
from .security import validate_production_environment

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = [host.strip() for host in os.environ["DJANGO_ALLOWED_HOSTS"].split(",")]
validate_production_environment(SECRET_KEY, ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DATABASE_PATH", "/app/data/db.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}
MIDDLEWARE = [*MIDDLEWARE]  # noqa: F405
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STATIC_URL = "/static/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
LOGIN_URL = "login"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
# The reverse proxy must overwrite this header and be the only public entry point.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if MAIL_ENABLED and not PUBLIC_BASE_URL.startswith('https://'):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('Email delivery in production requires an HTTPS PUBLIC_BASE_URL.')

# Avoid logging password-reset URLs, task content, IP addresses, or exception values.
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'private': {'()': 'tasks.observability.PrivateErrorFormatter'}},
    'handlers': {
        'private_console': {'class': 'logging.StreamHandler', 'formatter': 'private', 'level': 'ERROR'},
        'error_webhook': {'()': 'tasks.observability.ErrorWebhookHandler', 'endpoint': os.environ.get('ERROR_WEBHOOK_URL', '')},
    },
    'loggers': {
        'django': {'handlers': ['private_console', 'error_webhook'], 'level': 'ERROR', 'propagate': False},
        'django.server': {'handlers': ['private_console'], 'level': 'ERROR', 'propagate': False},
    },
}
