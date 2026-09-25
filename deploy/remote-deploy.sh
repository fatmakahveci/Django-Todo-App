#!/usr/bin/env bash
set -euo pipefail

deploy_path=$1
revision=$2
[[ "$deploy_path" =~ ^/[a-zA-Z0-9_/-]+$ && "$deploy_path" != / ]]
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
export APP_ENV_FILE="$deploy_path/.env"
export IMAGE="todo-app:$revision"
release_path="$deploy_path/releases/$revision"
test -s "$APP_ENV_FILE"

# Prevent concurrent deployments, including manually invoked deployments.
exec 9>"$deploy_path/deploy.lock"
flock -n 9
cd "$release_path"
sha256sum --check image.tar.gz.sha256
docker load --input image.tar.gz
compose=(docker compose --project-name todo-app --file "$release_path/compose.yml")
"${compose[@]}" run --rm --no-deps web python manage.py check --deploy

# Back up SQLite through its backup API so an active writer cannot corrupt the copy.
backup_name="pre-deploy-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
"${compose[@]}" run --rm --no-deps -e BACKUP_NAME="$backup_name" web python -c '
import os, pathlib, sqlite3
path = pathlib.Path("/app/data/db.sqlite3")
if path.exists():
    with sqlite3.connect(path) as source:
        with sqlite3.connect(path.parent / os.environ["BACKUP_NAME"]) as backup:
            source.backup(backup)
'
"${compose[@]}" run --rm --no-deps web python manage.py migrate --noinput
"${compose[@]}" up --detach --wait --wait-timeout 120
printf '%s\n' "$revision" > "$deploy_path/current-revision"
rm -- image.tar.gz image.tar.gz.sha256
