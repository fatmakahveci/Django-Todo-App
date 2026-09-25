# Project Layout

## Django Configuration

`config/` contains project-wide settings, root URL routing, and the ASGI/WSGI
entry points. The settings module is `config.settings`; deployment servers
should use `config.wsgi:application` or `config.asgi:application`.

Run management commands from the repository root using `python manage.py`.

## Task Application

`tasks/` owns task models, views, routes, and admin registration. Keep database
migrations in `tasks/migrations/` and templates in `tasks/templates/tasks/`.
The template namespace prevents collisions with templates from future apps.
Application CSS lives in `tasks/static/tasks/`; task form configuration lives in
`tasks/forms.py`. CI and production override settings in separate modules.

Account flows live in `tasks/accounts.py`, collection/trash/subtask actions in
`tasks/organize.py`, and shared recurrence logic in `tasks/services.py`. Preferences,
PWA responses, and privacy-preserving error events each have dedicated modules.
`tasks/management/commands/` contains operational commands; `tasks/locale/` contains
translation sources and compiled catalogs. After changing translated strings, run
`makemessages -l tr` and `compilemessages -l tr` (GNU gettext required) and commit both.
`deploy/systemd/` contains opt-in backup/reminder timers. See `docs/operations.md`.

Tests live in `tasks/tests/`, with filenames beginning with `test_`. Run the
suite with `python manage.py test` or just this app with
`python manage.py test tasks`.

Keep the `tasks` application name and existing migrations stable when moving
unrelated project files, since they identify database models and tables.

## Documentation and Repository Metadata

Keep the README, changelog, and license at the repository root. Put supporting
documentation in `docs/` and documentation images in `docs/assets/`.
GitHub workflows and contribution/security policies live in `.github/`.

`requirements.txt` is the shared dependency source for local setup and CI.

## Local Files

`.venv/`, environment files, caches, and SQLite databases are ignored by Git.
The existing `db.sqlite3` is preserved locally and removed from the Git index.
Historical commits may still contain old database copies; ignore rules do not
rewrite repository history.

For a fresh checkout, `python manage.py migrate` initializes the local database.
