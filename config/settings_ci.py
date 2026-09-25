"""Isolated database settings for CI and release validation."""

from .settings import *  # noqa: F403

# Never run CI migrations against the SQLite database included in old checkouts.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
