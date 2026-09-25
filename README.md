# Daymark · Django Todo App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Todo-App)](https://github.com/fatmakahveci/Django-Todo-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-web%20app-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A focused, responsive task workspace built with Django. Plan your day with
priorities, due dates, progress summaries, and private, user-owned tasks.

## Highlights

- Account registration, safe login redirects, and CSRF-protected logout
- Create, edit, complete, reopen, and delete your own tasks
- High / normal / low priorities and optional due dates
- Search titles and notes; filter open, completed, or overdue tasks
- Quick task capture directly from the dashboard with Enter
- Today / next-seven-days views and priority, due-date, or creation-date sorting
- List context preserved after editing or completing tasks
- Private JSON download of all your tasks
- Progress summaries and pagination for larger lists
- Responsive layout, keyboard focus styles, accessible form labels, and empty states
- Automatic import of legacy `base_task` records during migration
- Docker deployment, isolated CI databases, and database-aware health checks

## Technology

- Python
- Django
- SQLite
- Django Templates

## Getting Started

### Prerequisites

- Python 3.12–3.14
- pip

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Everyday Use

1. Register or sign in, then type a task into the quick-add field and press Enter.
2. Use **Edit** to add notes, a priority, and an optional due date.
3. Choose **Today** for open tasks due today, or **Next 7 days** for open tasks
   due tomorrow through seven days from today. Overdue tasks have their own view.
4. Choose a sort order and press **Apply**. Search matches titles and notes.
5. Complete a task using its circle button. Your current search, filter, and sort
   remain active; an emptied final page falls back to the last available page.
6. Use **Download my tasks** for a JSON copy of all your tasks, regardless of the
   active filter. This is a data export, not a full database backup or an import tool.

Dates use the configured server time zone, UTC by default. For local time,
set `DJANGO_TIME_ZONE` (for example `Europe/London` or `Europe/Istanbul`) before
starting Django; Docker deployments can set it in the server `.env` file.

### More Ways to Work

- Add an optional due date directly in the quick-add form.
- Combine the **No date** view with a **priority** filter, then press **Apply**.
- Choose **12, 24, or 48 tasks per page** alongside the sorting controls.
- Open task notes directly in the list using their expandable summary.
- From a task's detail page, **Duplicate task** copies its details into a new,
  incomplete task and opens the editor.
- For open tasks, **Move to tomorrow / next week** sets a date one or seven days
  from today. A task already scheduled later keeps its existing date.
- **Save & add another** opens a fresh form after creating a task.
- Download all your tasks as **JSON** or **CSV**. Formula-like CSV text is
  prefixed with an apostrophe for safer spreadsheet opening.
- On the dashboard, **Alt+Shift+N** focuses quick add and **Alt+Shift+F** focuses
  search. Shortcuts do nothing while typing in a form field; all actions also
  work without JavaScript using the visible controls.

## Quality Checks

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Repository Structure

```text
Django-Todo-App/
├── .github/              # CI workflows and contribution/security policies
├── config/               # Django settings, root URLs, ASGI and WSGI
├── docs/
│   └── assets/           # Documentation images
├── tasks/                # Task management application
│   ├── migrations/       # Database schema migrations
│   ├── static/tasks/     # Application stylesheet
│   ├── templates/tasks/  # Application templates
│   └── tests/            # Discoverable application tests
├── manage.py             # Django command entry point
└── requirements.txt      # Pinned runtime dependencies
```

See [project layout](docs/project-layout.md) for file placement conventions.
The local SQLite database (`db.sqlite3`) and virtual environment (`.venv/`)
are runtime files, not application source.

## Project Resources

- [CI and release delivery](docs/ci-cd.md)
- [Database upgrades and backups](docs/database-upgrades.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE.md)
