#!/usr/bin/env bash
set -euo pipefail
: "${DEPLOY_PATH:?Set DEPLOY_PATH}"
revision="$(cat "$DEPLOY_PATH/current-revision")"
[[ "$revision" =~ ^[a-f0-9]{40}$ ]]
export IMAGE="todo-app:$revision" APP_ENV_FILE="$DEPLOY_PATH/.env"
exec 9>"$DEPLOY_PATH/deploy.lock"
flock -n 9 || exit 0
docker compose --project-name todo-app -f "$DEPLOY_PATH/releases/$revision/compose.yml" exec -T web python manage.py send_reminders --send
