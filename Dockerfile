FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings_production
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 app \
    && mkdir /app/data \
    && chown app /app/data

COPY manage.py ./
COPY config/ ./config/
COPY tasks/ ./tasks/
COPY deploy/healthcheck.py ./deploy/healthcheck.py
# This build-only key is used for static collection, never for runtime sessions.
RUN DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
    CMD ["python", "deploy/healthcheck.py"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
