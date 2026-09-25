# CI and Release Delivery

## Continuous Integration

`.github/workflows/django.yml` runs on pushes and pull requests to `main`,
manual dispatch, and calls from the release workflow. It checks Python 3.12,
3.13, and 3.14 independently with the pinned runtime dependencies.

Each job checks dependency compatibility, Django configuration, missing
migrations, migration execution on an empty database, and the test suite.
`config.settings_ci` uses an in-memory database, preserving local data.
An additional Docker job builds the production image, runs migrations, and
checks database-aware HTTP readiness and admin static file delivery.

To run the same checks locally after installing requirements:

```bash
export DJANGO_SETTINGS_MODULE=config.settings_ci
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python -Wa manage.py test --noinput
unset DJANGO_SETTINGS_MODULE
```

## Release Delivery

`.github/workflows/publish-source-package.yml` runs when a GitHub release is
published or through manual dispatch. It first calls the CI workflow for the
same revision. Publication is skipped if any validation job fails.

After validation, it publishes a source archive and SHA-256 checksum as an OCI
artifact to `ghcr.io/<owner>/<repository>:<version>`. A leading `v` is removed
from release versions. Manual runs without a version use `sha-<commit-prefix>`.
`.gitattributes` excludes local databases and environment files from archives.

The publishing job uses the automatic `GITHUB_TOKEN` with `packages: write`;
validation jobs have only `contents: read`. Repository or organization policy
must permit package publication. An existing package must allow this repository
to write to it.

The source-package workflow remains separate from the SSH/Docker deployment
described below.

Commit and push the workflow files to activate them on GitHub. Configure branch
protection separately if all three Python checks must block merges.

## SSH / Docker Deployment

`.github/workflows/deploy.yml` runs on pushes to `main` and manual dispatches
from `main`. It validates the same revision, builds a Docker image, transfers
it over verified SSH, and starts it with Docker Compose. Deployments are
serialized. No container registry credentials are needed for this path.

### One-time server setup

Use an x86-64 Linux server with Docker Engine, Docker Compose v2 supporting
`up --wait`, Bash, `flock`, and `sha256sum`. The SSH user must be able to run
Docker without interactive sudo and write to the deployment directory, for
example `/opt/todo-app`. Docker access grants administrator-level capabilities;
use a dedicated deployment account and key.

1. Create the deployment directory with ownership assigned to that account.
2. Copy `deploy/.env.example` to `/opt/todo-app/.env`, restrict it to mode 600,
   and replace every placeholder. Generate a unique secret with
   `openssl rand -hex 32`. Use explicit domain names, not `*`, in allowed hosts.
3. Configure an HTTPS reverse proxy on the host pointing to
   `http://127.0.0.1:8000`. Preserve `Host`, overwrite `X-Forwarded-Proto` with
   the request scheme, and redirect public HTTP requests to HTTPS. Also overwrite
   `X-Real-IP` with the actual client IP and set `AUTH_TRUSTED_PROXIES` in the server
   `.env` to the proxy source IP/CIDR seen by the container. Never trust arbitrary
   forwarded headers or use a wildcard proxy network. Without this configuration,
   requests behind one proxy share its IP throttle budget. Set the proxy request
   body limit to 64 KiB as well.
4. Add the deployment public key to the account's `authorized_keys`.

Create the GitHub environment **production** with these settings:

| Type | Name | Value |
| --- | --- | --- |
| Variable | `SSH_HOST` | Server IPv4 address or DNS name |
| Variable | `SSH_USER` | Deployment account |
| Variable | `SSH_PORT` | SSH port; defaults to `22` |
| Variable | `DEPLOY_PATH` | Absolute path, e.g. `/opt/todo-app` |
| Secret | `SSH_PRIVATE_KEY` | Private key for that account |
| Secret | `SSH_KNOWN_HOSTS` | Verified server host-key entry in known_hosts format |

Obtain the server host key through a trusted channel; do not blindly trust an
unverified `ssh-keyscan` result. For nonstandard ports use the corresponding
`[hostname]:port` known_hosts entry. Paths must contain only letters, digits,
underscores, hyphens, and slashes. Use environment protection rules to limit
deployments to `main` if desired.

### Runtime and persistence

The container runs Gunicorn as an unprivileged user with production settings;
WhiteNoise serves collected static files. Only the host loopback port is exposed.
Production checks may report `security.W005` and `security.W021`: HSTS coverage
for every subdomain and browser preloading are intentionally left disabled until
the domain owner can confirm their prerequisites.
SQLite lives in the named volume `todo-app_app-data`, which survives container
replacement. The repository database is never copied into the image.

The remote script verifies the transferred checksum, checks production settings,
backs up an existing database inside the data volume, applies migrations, and
waits up to 120 seconds for container health. It records the successful commit
in `/opt/todo-app/current-revision`. The legacy import migration copies `base_task` records into an empty new task
table. Conflicting nonempty histories stop the migration without overwriting data.

Backups in the same volume do not protect against server or disk loss; copy them
off-host and define a retention policy. Do not run `docker compose down -v` on
this project unless intentionally deleting its data.

### Failure and recovery

Inspect failures with `docker compose --project-name todo-app --file
/opt/todo-app/releases/<commit>/compose.yml logs`, setting `IMAGE` and
`APP_ENV_FILE` as below. A failed health check fails the workflow; rollback is
not automatic, and migrations may already have changed the database.

To restore a previous application image, first verify its compatibility with
the current schema, then run on the server:

```bash
export APP_ENV_FILE=/opt/todo-app/.env
export IMAGE=todo-app:<previous-commit>
docker compose --project-name todo-app \
  --file /opt/todo-app/releases/<previous-commit>/compose.yml \
  up --detach --wait --wait-timeout 120
```

Retained release directories and Docker images support manual rollback; clean
them up according to your retention policy. Restore a database backup only as
a deliberate recovery step, since that discards changes after the backup.

Regression tests cover task ownership, escaped search inputs, CSRF protection,
login/logout flows, filtering, pagination, and legacy database imports. Passing
CI is not a substitute for reviewing deployment configuration and access policy.
