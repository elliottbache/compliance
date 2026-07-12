#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

MODE="docker"
ENV_FILE="$DEFAULT_ENV_FILE"
COMPOSE_FILE="$DEFAULT_COMPOSE_FILE"
OUTPUT_DIR="$DEFAULT_DB_BACKUP_DIR"
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 [options]

Create a PostgreSQL custom-format database backup.

Options:
  --compose-file PATH     Docker Compose file. Defaults to $DEFAULT_COMPOSE_FILE.
  --output-dir PATH       Backup output directory. Defaults to $DEFAULT_DB_BACKUP_DIR.
$(usage_common_modes)

Examples:
  $0
  $0 --mode host --env-file backend/.env --output-dir /tmp
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
        --output-dir)
            OUTPUT_DIR="${2:-}"
            shift 2
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

load_env_file "$ENV_FILE"
require_db_env
ensure_dir "$OUTPUT_DIR"

BACKUP_FILE="$OUTPUT_DIR/compliance-db-${POSTGRES_DB}-$(timestamp).dump"

if [ "$MODE" = "docker" ]; then
    require_command docker
    require_file "$COMPOSE_FILE"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: docker compose -f $COMPOSE_FILE exec -T postgres sh -c 'pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Fc' > $BACKUP_FILE"
    else
        docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
            'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP_FILE"
    fi
else
    require_command pg_dump
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: PGPASSWORD=<redacted> pg_dump -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -Fc -f $BACKUP_FILE"
    else
        PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
            -h "$POSTGRES_HOST" \
            -p "$POSTGRES_PORT" \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            -Fc \
            -f "$BACKUP_FILE"
    fi
fi

log "Database backup written to: $BACKUP_FILE"
