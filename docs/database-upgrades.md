# Database Upgrades and Backups

Run `python manage.py migrate` before starting an updated checkout. New installs
create an empty task database; existing installs gain priority and due-date
fields without resetting their tasks.

## Legacy application name

Migration `0002_import_legacy_tasks` detects the old `base_task` table and copies
its rows into an empty `tasks_task` table. It preserves IDs, user ownership,
titles, descriptions, completion status, and creation timestamps. The original
table remains intact as a historical snapshot; it is not used by the app.

If both tables already contain rows, the migration stops rather than guessing
which records to keep. Back up the database and reconcile the two histories
explicitly. Re-running a successfully applied migration does not import again.
Rolling back this import migration alone does not delete the copied records.

## Local backups

Before upgrading an existing SQLite database, create a consistent backup using
SQLite's backup API, especially when the application may still be writing:

```bash
python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

Path("backups").mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
with sqlite3.connect("file:db.sqlite3?mode=ro", uri=True) as source:
    with sqlite3.connect(f"backups/todo-{stamp}.sqlite3") as target:
        source.backup(target)
PY
python manage.py migrate
```

Keep backups private and copy important backups off-host. Git ignores local
backups. The Docker deployment script creates a backup before each migration;
see [deployment documentation](ci-cd.md) for recovery details.

For an isolated development database, set `DJANGO_DATABASE_PATH` to another
SQLite file before running migrations or starting the server.
