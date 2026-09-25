# Operating Daymark

The repository contains the deployment and scheduled-job configuration. Live
activation requires your server, verified SSH host key, SMTP service, and off-host
backup destination. No credentials or external services are provisioned by this code.

## HTTPS deployment

Follow [CI/CD setup](ci-cd.md). `deploy/nginx.conf.example` is a template: replace
its hostname and certificate paths, obtain a certificate, validate with `nginx -t`,
and enable it on your server. It deliberately disables access logging so reset
links and IP addresses do not enter proxy access logs. Gunicorn logs only request
method, response status, and duration. Production configuration fails closed if
email is enabled without an HTTPS `PUBLIC_BASE_URL`.

## Backup and restore rehearsal

For local SQLite, these commands refuse to overwrite existing output files:

```bash
python manage.py backup_database --output backups/manual.sqlite3
python manage.py verify_backup --source backups/manual.sqlite3 --output backups/restored-copy.sqlite3
```

The first uses SQLite's consistent backup API and checks database integrity. The
second restores into a **new** database file and checks it again. Both create
mode-600 files. Neither restores over your live database. Test application startup
against a restored copy before any real recovery.

On your Linux server, install Restic and Python 3.11+ alongside the Docker/Compose
prerequisites. Create an encrypted Restic repository on another host or an object
storage service; keep the repository password separately from the server backup.
Configure any provider credentials using its normal environment/file mechanism.
Set `/etc/daymark-backup.env` to mode 600, for example:

```ini
DEPLOY_PATH=/opt/todo-app
RESTIC_REPOSITORY=sftp:backup-user@backup.example.com:/srv/daymark
RESTIC_PASSWORD_FILE=/etc/daymark-restic-password
```

Initialize the repository once with `restic init` using the same configuration.
Copy `deploy/backup-offsite.sh` and `deploy/send-reminders.sh` to
`/opt/daymark-tools/`, and the supplied service/timer units to `/etc/systemd/system/`.
The units use the system account running systemd (root by default); restrict these
files to administrators. The backup job must be able to read its repository
credentials and run Docker. Its lock is shared with deployment.

```bash
sudo systemctl daemon-reload
sudo systemctl start daymark-backup.service
sudo journalctl -u daymark-backup.service --no-pager
sudo systemctl enable --now daymark-backup.timer
```

Every daily run creates a checked SQLite backup, encrypts/uploads it with Restic,
checks the repository, downloads the latest tagged snapshot, compares SHA-256
hashes, and checks the downloaded SQLite file. Staging files are removed when the
job exits; checked local snapshots remain under `/app/data/backups/`. A failed
upload or restore test fails the job. Inspect failed services and disk usage;
retention/deletion is deliberately an operator decision. Configure alerts for
failed systemd units through your chosen monitoring service.

For recovery, list snapshots with `restic snapshots --tag daymark`, select the
specific snapshot ID, and restore to a new directory. Inspect the result and run
`verify_backup` against it. Stop writers before an actual live database replacement;
that replacement discards all changes after the chosen backup and is a separate
recovery decision. Keep a fresh pre-recovery copy and match the application version
to the backup's schema.

References: [Restic backup](https://restic.readthedocs.io/en/stable/040_backup.html),
[Restic restore](https://restic.readthedocs.io/en/stable/050_restore.html).

## Accounts and mail

Set `MAIL_ENABLED=true`, `PUBLIC_BASE_URL`, `DEFAULT_FROM_EMAIL`, and the SMTP
variables from `deploy/.env.example`. SMTP uses STARTTLS and a ten-second timeout.
Restart the application after changing environment values. With mail disabled,
the UI reports delivery as unavailable; password changes remain usable.

Users can change passwords in Account settings, or request a reset from Sign in.
Reset links expire after one hour and use the configured canonical origin.
Responses do not disclose whether an email exists. Changing an email requires the
current password and clears verification and reminder opt-in. Verification links
expire after 24 hours, belong to the signed-in account, and require a confirmation
POST. Mail endpoints share the authentication throttle.

## Optional reminders

A user must verify their email and explicitly enable reminders in Account settings.
Choose a language, timezone, and local hour. The hourly job sends a count of open,
active tasks due today or overdue; task titles and notes are omitted. Delivery is
at or after the selected hour, once per local calendar day. Subtask completion is
independent of parent completion.

```bash
python manage.py send_reminders         # Preview eligible count; sends nothing
python manage.py send_reminders --send  # Explicit delivery
sudo systemctl enable --now daymark-reminders.timer
```

The systemd job reads the deployment path from `/etc/daymark-backup.env` and SMTP
settings from the running container. Database claims prevent duplicate daily
sends across scheduler runs. A failed/uncertain send retains an unsent claim to
avoid duplicates after SMTP timeouts. Inspect `ReminderDelivery` records with a
null `sent_at`; retry only after checking the provider, by removing that specific
claim and rerunning the job. A crash can result in a missed reminder, not a promise
of exactly-once delivery. Changing timezone does not reset existing dated claims.

## Errors and monitoring

Production Django errors are JSON records with `event`, `error_id`, HTTP `method`,
`status`, and exception **class name**. No request URL, query string, body, cookie,
IP address, email, task content, exception message, or traceback is included. A 500
page and `X-Error-ID` response header provide a support reference.

Optionally set `ERROR_WEBHOOK_URL` to an HTTPS receiver accepting this JSON:

```json
{"event":"application_error","error_id":"opaque-id","status":500,"method":"POST","exception":"ValueError"}
```

External notifications are limited to one per minute per worker, time out after
two seconds, and refuse redirects. Delivery failure does not replace the original
response; console records remain available. This endpoint is a generic receiver,
not a Sentry/Slack DSN. Leave empty until a compatible service is selected.
Use an external uptime check for `/healthz/`; process/server outages cannot report
themselves through application error handling.

## Mobile installation

Use the browser's Install/Add to Home Screen option. Supporting Chromium browsers
also expose an **Install app** button. HTTPS is required outside localhost.
Only static icons and a generic offline page are cached. Tasks and account pages
always require a network connection; there is no offline task editing or background
sync. See [PWA installation requirements](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).

## Release validation

The automated suite covers ownership, trash/restore, collection isolation,
month-end recurrence, subtasks, verification/reset, reminders, Turkish UI, PWA
routes, backup restoration, and private error events. The release was also checked
in headless Chromium at 375, 768, and 1280 pixels with sample data: no horizontal
overflow or JavaScript errors on dashboard, editor, account, collections, and trash.
Language switching and offline fallback were exercised. Native iOS/Android install
prompts and real SMTP/remote backup delivery still require target-device/service
checks once configured.
