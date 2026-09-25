#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${DEPLOY_PATH:?Set DEPLOY_PATH}"
: "${RESTIC_REPOSITORY:?Set an off-host Restic repository}"
: "${RESTIC_PASSWORD_FILE:?}"
revision=$(cat "$DEPLOY_PATH/current-revision")
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
export IMAGE="todo-app:$revision" APP_ENV_FILE="$DEPLOY_PATH/.env"
compose=(docker compose --project-name todo-app --file "$DEPLOY_PATH/releases/$revision/compose.yml")
exec 9>"$DEPLOY_PATH/deploy.lock"
flock -n 9
stamp=$(date -u +%Y%m%dT%H%M%SZ)
remote_file="/app/data/backups/$stamp.sqlite3"
staging=$(mktemp -d)
trap 'rm -rf -- "$staging"' EXIT
"${compose[@]}" exec -T web python manage.py backup_database --output "$remote_file"
"${compose[@]}" cp "web:$remote_file" "$staging/daymark.sqlite3"
# A stable filename keeps snapshot paths predictable despite temporary staging dirs.
restic backup --stdin --stdin-filename daymark.sqlite3 --tag daymark < "$staging/daymark.sqlite3"
restic check
restic dump --tag daymark latest /daymark.sqlite3 > "$staging/restored.sqlite3"
python3 - "$staging/daymark.sqlite3" "$staging/restored.sqlite3" <<'PYTHON'
import hashlib, sqlite3, sys
from pathlib import Path
original, restored = map(Path, sys.argv[1:])
with original.open('rb') as source, restored.open('rb') as target:
    if hashlib.file_digest(source, 'sha256').digest() != hashlib.file_digest(target, 'sha256').digest():
        raise SystemExit('Restored backup does not match the source.')
with sqlite3.connect(restored.as_uri() + '?mode=ro', uri=True) as database:
    if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Restored database integrity check failed.')
print('Off-host restore rehearsal passed.')
PYTHON
# Remote retention/deletion is an explicit operator decision, never automatic here.
