#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

MODE="docker"
ENV_FILE="$DEFAULT_ENV_FILE"
COMPOSE_FILE="$DEFAULT_COMPOSE_FILE"
BACKUP_FILE=""
CONFIRM_RESTORE=0
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 --file BACKUP.dump --confirm-restore [options]

Restore a PostgreSQL custom-format database backup.

Options:
  --file PATH             Backup file created by backup-db.sh.
  --confirm-restore       Required. Confirms destructive database restore.
  --compose-file PATH     Docker Compose file. Defaults to $DEFAULT_COMPOSE_FILE.
$(usage_common_modes)

Examples:
  $0 --file /var/backups/compliance/db/compliance-db-compliance_prod-20260101T120000Z.dump --confirm-restore
  $0 --mode host --env-file backend/.env --file /tmp/backup.dump --confirm-restore
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mode)
            MODE="${2:-}"
            shift 2
            ;;
        --env-file)
            ENV_FILE="${2:-}"
            shift 2
            ;;
        --compose-file)
            COMPOSE_FILE="${2:-}"
            shift 2
            ;;
        --file)
            BACKUP_FILE="${2:-}"
            shift 2
            ;;
        --confirm-restore)
            CONFIRM_RESTORE=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

[ "$MODE" = "docker" ] || [ "$MODE" = "host" ] || die "--mode must be docker or host"
[ "$CONFIRM_RESTORE" = "1" ] || die "Refusing to restore without --confirm-restore"
[ -n "$BACKUP_FILE" ] || die "--file is required"
require_file "$BACKUP_FILE"

load_env_file "$ENV_FILE"
require_db_env

if [ "$MODE" = "docker" ]; then
    require_command docker
    require_file "$COMPOSE_FILE"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: cat $BACKUP_FILE | docker compose -f $COMPOSE_FILE exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"'"
    else
        docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
            'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$BACKUP_FILE"
    fi
else
    require_command pg_restore
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: PGPASSWORD=<redacted> pg_restore --clean --if-exists --no-owner -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB $BACKUP_FILE"
    else
        PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
            --clean \
            --if-exists \
            --no-owner \
            -h "$POSTGRES_HOST" \
            -p "$POSTGRES_PORT" \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            "$BACKUP_FILE"
    fi
fi

log "Database restored from: $BACKUP_FILE"
