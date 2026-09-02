# Django Todo App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Todo-App)](https://github.com/fatmakahveci/Django-Todo-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-web%20app-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A server-rendered task manager built with Django class-based views and per-user task ownership.

## Highlights

- Account registration, login, and logout
- Create, view, update, complete, and delete tasks
- User-scoped task lists protected by authentication
- Django templates and SQLite persistence

## Technology

- Python
- Django
- SQLite
- Django Templates

## Getting Started

### Prerequisites

- Python 3.11 or newer
- pip

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Django
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Quality Checks

```bash
python manage.py check
python manage.py test
```

## Repository Structure

- `base` — task model, class-based views, routes, and templates
- `django_todo_app` — project configuration
- `manage.py` — Django command entry point

## Project Resources

- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE.md)
