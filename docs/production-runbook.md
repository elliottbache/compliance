# Production Runbook

Operational procedures for a staging or production Docker deployment. Run these
commands over SSH on the deployment server unless a step explicitly says
otherwise.

## Install

Install Docker and the Docker Compose plugin using the operating system's
supported package path.

Create the host directory layout:

```bash
sudo mkdir -p /opt/compliance
sudo mkdir -p /etc/compliance
sudo mkdir -p /var/lib/compliance/attachments
sudo mkdir -p /var/lib/compliance/caddy/data
sudo mkdir -p /var/lib/compliance/caddy/config
sudo mkdir -p /var/lib/compliance/ollama
sudo mkdir -p /var/lib/compliance/postgres
sudo mkdir -p /var/backups/compliance/db
sudo mkdir -p /var/backups/compliance/attachments
sudo mkdir -p /var/log/compliance/backend
sudo chown -R "$USER":"$USER" /opt/compliance
sudo chown -R "$USER":"$USER" /etc/compliance
sudo chown -R "$USER":"$USER" /var/lib/compliance
sudo chown -R "$USER":"$USER" /var/backups/compliance
sudo chown -R "$USER":"$USER" /var/log/compliance
```

Place the application under `/opt/compliance/app`:

```bash
cd /opt/compliance
git clone https://github.com/elliottbache/compliance.git app
cd /opt/compliance/app
```

For release-bundle deployments, extract or copy the bundle contents to
`/opt/compliance/app` instead of cloning from Git.

## Configure

Create and lock down the deployment environment file:

```bash
cp docker/.env.example /etc/compliance/.env
chmod 600 /etc/compliance/.env
```

Edit `/etc/compliance/.env`. At minimum, set:

```ini
APP_ENV=production
COMPLIANCE_HOSTNAME=compliance.internal
POSTGRES_PASSWORD=replace_with_a_strong_database_password
POSTGRES_HOST=postgres
ATTACHMENTS_DIR=/app/data/attachments
CORS_ORIGIN=https://compliance.internal
SECRET_KEY=replace_with_a_long_random_secret
AI_MODE=anthropic
AI_MODEL=claude-haiku-4-5-20251001
AI_LOG_PROMPTS=false
LOG_TO_FILE=false
ANTHROPIC_API_KEY=replace_with_provider_key
OLLAMA_BASE_URL=http://ollama:11434
MALWARE_SCANNING_ENABLED=true
MALWARE_SCANNER_HOST=clamav
MALWARE_SCANNER_PORT=3310
```

For local Ollama-backed AI, use:

```ini
AI_MODE=local
AI_MODEL=qwen3:4b
AI_LOG_PROMPTS=false
LOG_TO_FILE=false
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://ollama:11434
```

Production Compose also sets `LOG_TO_FILE=false` for the backend container.
Use `docker compose logs` for operational logs; Docker's `local` log driver
rotates those container logs according to `docker-compose.prod.yaml`.

Configure internal DNS so `COMPLIANCE_HOSTNAME` resolves to the deployment
server's LAN IP. Allow inbound `80/tcp` and `443/tcp` to the deployment server.
Client machines may need to trust Caddy's internal CA certificate from:

```text
/var/lib/compliance/caddy/data/caddy/pki/authorities/local/root.crt
```

## Run Migrations

Start PostgreSQL and run Alembic migrations:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml up -d postgres
docker compose -f docker-compose.prod.yaml run --rm backend python -m alembic -c backend/alembic.ini upgrade head
```

## Create First Admin

Create the first admin account after migrations have run:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml run --rm backend python -m compliance.cli bootstrap-admin --full-name "Admin User" --email admin@example.com
```

The command prompts for the password twice without echoing it. If an active
admin already exists, it exits successfully without creating another account.

## Create User

Routine users are created through the admin-only `POST /api/users` API. There
is no dedicated production CLI for routine user creation. Supported roles are
`admin`, `inspector`, `reviewer`, and `viewer`.

## Change Password

The application does not yet provide a self-service password change endpoint or
frontend flow. Until that exists, use the manual password reset procedure below
when a user must change their password.

## Disable User

The application does not yet provide an admin disable-user endpoint or frontend
flow. To disable an account during operations, back up first and update the
user through the backend container:

```bash
cd /opt/compliance/app
scripts/backup-db.sh

docker compose -f docker-compose.prod.yaml run --rm backend python - <<'PY'
from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance.db.db_access import get_engine
from compliance.db.models import User

email = "user@example.com"

with Session(get_engine()) as session:
    user = session.execute(select(User).where(User.email == email)).scalars().first()
    if user is None:
        raise SystemExit(f"No user found for {email}")
    user.is_active = False
    session.commit()
    print(f"Disabled {email}")
PY
```

Disabling a user prevents new authenticated requests after the user's current
token expires or when the backend checks active-user status. It does not delete
the account or its audit history.

## Reset Password

The application does not yet provide an admin password reset endpoint or
frontend flow. To reset a user's password manually, back up first and run the
hash update inside the backend container so the application password hasher is
used:

```bash
cd /opt/compliance/app
scripts/backup-db.sh

docker compose -f docker-compose.prod.yaml run --rm backend python - <<'PY'
import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance.auth.authentication import _hash_password
from compliance.db.db_access import get_engine
from compliance.db.models import User

email = "user@example.com"
password = getpass.getpass("New password: ")
confirmation = getpass.getpass("Confirm new password: ")

if not password:
    raise SystemExit("Password cannot be empty")
if password != confirmation:
    raise SystemExit("Passwords do not match")

with Session(get_engine()) as session:
    user = session.execute(select(User).where(User.email == email)).scalars().first()
    if user is None:
        raise SystemExit(f"No user found for {email}")
    user.hashed_password = _hash_password(password)
    user.is_active = True
    session.commit()
    print(f"Reset password for {email}")
PY
```

Have the user sign in with the new password immediately. Do not send passwords
through chat, tickets, logs, or command-line arguments.

## Lost-Admin Recovery

Use this only when no operator can sign in with an active admin account. Back up
first, then either reset an existing admin password or promote a known active
user to admin.

To reset an existing admin password, use the manual password reset procedure
above with the admin's email address.

To promote an existing active user to admin:

```bash
cd /opt/compliance/app
scripts/backup-db.sh

docker compose -f docker-compose.prod.yaml run --rm backend python - <<'PY'
from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance.db.db_access import get_engine
from compliance.db.models import Role, User

email = "user@example.com"

with Session(get_engine()) as session:
    user = session.execute(select(User).where(User.email == email)).scalars().first()
    if user is None:
        raise SystemExit(f"No user found for {email}")
    user.role = Role.ADMIN
    user.is_active = True
    session.commit()
    print(f"Promoted {email} to admin")
PY
```

After recovery, sign in through `https://compliance.internal`, create or repair
the intended admin accounts, and document the incident. The
`bootstrap-admin` command is only for first installation; it will not create a
new admin while any active admin already exists.

## Start

Start the production stack:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml up -d --build
```

For local-AI deployments:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml --profile local-ai up -d ollama
docker compose -f docker-compose.prod.yaml --profile local-ai run --rm ollama-init
docker compose -f docker-compose.prod.yaml --profile local-ai up -d --build
```

## Stop

Stop running containers without deleting persistent data:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml stop
```

## Restart

Restart the stack after config changes or maintenance:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml up -d --build
```

For local-AI deployments, include `--profile local-ai`.

## Check Health

Check the public route through Caddy:

```bash
curl -f https://compliance.internal/api/health/live
curl -f https://compliance.internal/api/health/ready
```

Check container health and recent logs:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml ps
docker compose -f docker-compose.prod.yaml logs --tail=100 backend
docker compose -f docker-compose.prod.yaml logs --tail=100 frontend
```

## Backup

Run database and attachment backups:

```bash
cd /opt/compliance/app
scripts/backup-db.sh
scripts/backup-attachments.sh
ls -lh /var/backups/compliance/db
ls -lh /var/backups/compliance/attachments
```

Copy `/var/backups/compliance` to off-server storage after each backup.

## Backup Schedule

Install the example systemd timers to run daily local backups, prune old local
backup files, and smoke-test the latest backup artifacts weekly:

```bash
cd /opt/compliance/app
sudo cp ops/systemd/compliance-backup.service /etc/systemd/system/
sudo cp ops/systemd/compliance-backup.timer /etc/systemd/system/
sudo cp ops/systemd/compliance-restore-test.service /etc/systemd/system/
sudo cp ops/systemd/compliance-restore-test.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now compliance-backup.timer
sudo systemctl enable --now compliance-restore-test.timer
systemctl list-timers 'compliance-*'
```

The backup timer uses `BACKUP_RETENTION_DAYS=30` by default. Edit
`/etc/systemd/system/compliance-backup.service` and reload systemd if the local
retention window needs to change:

```bash
sudo systemctl daemon-reload
sudo systemctl restart compliance-backup.timer
```

Preview retention cleanup manually before deleting old files:

```bash
cd /opt/compliance/app
scripts/prune-backups.sh --keep-days 30 --dry-run
```

Local retention only controls files under `/var/backups/compliance`. Off-server
backup storage should have its own retention and encryption policy.

## Restore Test

Run the restore smoke test to validate that the newest PostgreSQL dump and
attachment archive are readable without overwriting production data:

```bash
cd /opt/compliance/app
scripts/restore-test.sh
```

This does not replace a full restore test. At least monthly, and after backup,
restore, schema, or storage changes, restore a recent backup into staging or a
temporary environment and confirm `/api/health/ready`, representative records,
and representative attachment downloads.

## Restore

Restore commands are destructive and require `--confirm-restore`. Dry-run first:

```bash
cd /opt/compliance/app
scripts/restore-db.sh --file /var/backups/compliance/db/compliance-db-compliance_prod-20260101T120000Z.dump --confirm-restore --dry-run
scripts/restore-attachments.sh --file /var/backups/compliance/attachments/compliance-attachments-20260101T120000Z.tar.gz --confirm-restore --dry-run
```

Run the restore:

```bash
scripts/restore-db.sh --file /var/backups/compliance/db/compliance-db-compliance_prod-20260101T120000Z.dump --confirm-restore
scripts/restore-attachments.sh --file /var/backups/compliance/attachments/compliance-attachments-20260101T120000Z.tar.gz --confirm-restore
```

Restart and check health:

```bash
docker compose -f docker-compose.prod.yaml up -d --build
curl -f https://compliance.internal/api/health/ready
```

## Upgrade

Back up before changing code or schema:

```bash
cd /opt/compliance/app
scripts/backup-db.sh
scripts/backup-attachments.sh
```

Update the application source:

```bash
git fetch --tags origin
git checkout v0.4.0
```

For release-bundle deployments, replace `/opt/compliance/app` with the new
bundle contents while preserving `/etc/compliance/.env`, `/var/lib/compliance`,
and `/var/backups/compliance`.

Run migrations and restart:

```bash
docker compose -f docker-compose.prod.yaml up -d postgres
docker compose -f docker-compose.prod.yaml run --rm backend python -m alembic -c backend/alembic.ini upgrade head
docker compose -f docker-compose.prod.yaml up -d --build
curl -f https://compliance.internal/api/health/ready
```

For local-AI deployments, run `ollama-init` and include `--profile local-ai` in
the final `up` command.

## Rebuild Or Update Images

Use this procedure when updating base images or third-party service images
without changing application code. For application releases that include schema
or source changes, use the full upgrade procedure above instead.

Back up first:

```bash
cd /opt/compliance/app
scripts/backup-db.sh
scripts/backup-attachments.sh
```

Pull updated third-party service images and rebuild application images from the
latest configured base images:

```bash
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml build --pull
docker compose -f docker-compose.prod.yaml up -d
curl -f https://compliance.internal/api/health/ready
```

For local-AI deployments, include the profile:

```bash
docker compose -f docker-compose.prod.yaml --profile local-ai pull
docker compose -f docker-compose.prod.yaml --profile local-ai build --pull
docker compose -f docker-compose.prod.yaml --profile local-ai up -d
curl -f https://compliance.internal/api/health/ready
```

Check recent container logs before considering the update complete:

```bash
docker compose -f docker-compose.prod.yaml ps
docker compose -f docker-compose.prod.yaml logs --tail=100 backend
docker compose -f docker-compose.prod.yaml logs --tail=100 frontend
docker compose -f docker-compose.prod.yaml logs --tail=100 postgres
```

If health fails after an image update, capture logs, return to the previous
known-good release or image pins, rebuild, restart, and re-run
`/api/health/ready`.

## Vulnerability Scan Review

Before promoting a release or running an image-only update in production, review
the latest `Security Scan` workflow result in GitHub Actions. The workflow runs
weekly and on dependency, Docker, and workflow changes.

The scan fails on high or critical findings from:

- `pip-audit` for Python dependencies.
- `npm audit --audit-level=high` for frontend dependencies.
- Trivy filesystem scanning.
- Trivy scanning of the built backend and frontend Docker images.

If the scan fails, review the affected package or image layer, update the
dependency or image pin, rebuild, and re-run the workflow before deploying.

## Rotate Secrets

Back up first, then edit `/etc/compliance/.env`:

```bash
cd /opt/compliance/app
scripts/backup-db.sh
scripts/backup-attachments.sh
chmod 600 /etc/compliance/.env
```

Rotate one secret at a time when possible. After editing, restart and check
health:

```bash
docker compose -f docker-compose.prod.yaml up -d --force-recreate backend frontend
curl -f https://compliance.internal/api/health/ready
```

Rotating `SECRET_KEY` invalidates existing JWT sessions. Rotating
`POSTGRES_PASSWORD` also requires updating the PostgreSQL role password inside
the database before restarting the backend.

## Debug Failed Uploads

Check the backend logs:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml logs --tail=200 backend
```

Check storage and permissions:

```bash
ls -ld /var/lib/compliance/attachments
df -h /var/lib/compliance
```

If malware scanning is enabled, check ClamAV:

```bash
docker compose -f docker-compose.prod.yaml ps clamav
docker compose -f docker-compose.prod.yaml logs --tail=100 clamav
```

Confirm `/etc/compliance/.env` contains:

```ini
ATTACHMENTS_DIR=/app/data/attachments
MALWARE_SCANNER_HOST=clamav
MALWARE_SCANNER_PORT=3310
```

## Debug Failed Login

Check backend logs for authentication or database errors:

```bash
cd /opt/compliance/app
docker compose -f docker-compose.prod.yaml logs --tail=200 backend
```

Confirm the backend is ready:

```bash
curl -f https://compliance.internal/api/health/ready
```

Common causes:

- Incorrect email or password.
- User account is inactive.
- `SECRET_KEY` changed, invalidating existing sessions.
- Database is unavailable or migrations did not run.
- Browser is calling the wrong origin; use `https://COMPLIANCE_HOSTNAME`.
