"""Fail closed when deployment secrets or hosts are unsafe."""

from django.core.exceptions import ImproperlyConfigured


def validate_production_environment(secret, hosts):
    if len(secret) < 50 or len(set(secret)) < 10 or secret.startswith('django-insecure-') or 'replace-with' in secret:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a unique random secret of at least 50 characters.')
    if not hosts or any(not host or '*' in host or '/' in host or host.startswith('.') for host in hosts):
        raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain explicit hostnames, without wildcards or schemes.')
