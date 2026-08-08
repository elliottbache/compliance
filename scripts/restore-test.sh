#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

MODE="docker"
COMPOSE_FILE="$DEFAULT_COMPOSE_FILE"
DB_DIR="$DEFAULT_DB_BACKUP_DIR"
ATTACHMENTS_DIR="$DEFAULT_ATTACHMENTS_BACKUP_DIR"
DB_FILE=""
ATTACHMENTS_FILE=""
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 [options]

Validate that recent database and attachment backups are readable.

Options:
  --mode docker|host       Runtime mode for PostgreSQL tools. Defaults to docker.
  --compose-file PATH      Docker Compose file. Defaults to $DEFAULT_COMPOSE_FILE.
  --db-dir PATH            Database backup directory. Defaults to $DEFAULT_DB_BACKUP_DIR.
  --attachments-dir PATH   Attachment backup directory. Defaults to $DEFAULT_ATTACHMENTS_BACKUP_DIR.
  --db-file PATH           Specific database backup to validate.
  --attachments-file PATH  Specific attachment backup to validate.
  --dry-run                Print checks without running them.
  -h, --help               Show help.

Examples:
  $0
  $0 --mode host --db-file /tmp/compliance-db.dump --attachments-file /tmp/compliance-attachments.tar.gz
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mode)
            MODE="${2:-}"
            shift 2
            ;;
        --compose-file)
            COMPOSE_FILE="${2:-}"
            shift 2
            ;;
        --db-dir)
            DB_DIR="${2:-}"
            shift 2
            ;;
        --attachments-dir)
            ATTACHMENTS_DIR="${2:-}"
            shift 2
            ;;
        --db-file)
            DB_FILE="${2:-}"
            shift 2
            ;;
        --attachments-file)
            ATTACHMENTS_FILE="${2:-}"
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

latest_file() {
    local dir="$1"
    local pattern="$2"

    require_dir "$dir"
    find "$dir" -type f -name "$pattern" -printf '%T@ %p\n' \
        | sort -nr \
        | head -n 1 \
        | cut -d ' ' -f 2-
}

if [ -z "$DB_FILE" ]; then
    DB_FILE="$(latest_file "$DB_DIR" "compliance-db-*.dump")"
fi

if [ -z "$ATTACHMENTS_FILE" ]; then
    ATTACHMENTS_FILE="$(latest_file "$ATTACHMENTS_DIR" "compliance-attachments-*.tar.gz")"
fi

[ -n "$DB_FILE" ] || die "No database backup found in: $DB_DIR"
[ -n "$ATTACHMENTS_FILE" ] || die "No attachment backup found in: $ATTACHMENTS_DIR"
require_file "$DB_FILE"
require_file "$ATTACHMENTS_FILE"

log "Validating database backup: $DB_FILE"
if [ "$MODE" = "docker" ]; then
    require_command docker
    require_file "$COMPOSE_FILE"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: stream $DB_FILE into postgres container and run pg_restore --list"
    else
        docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c '
            tmp="$(mktemp)"
            trap "rm -f \"$tmp\"" EXIT
            cat > "$tmp"
            pg_restore --list "$tmp" >/dev/null
        ' < "$DB_FILE"
    fi
else
    require_command pg_restore
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY RUN: pg_restore --list $DB_FILE >/dev/null"
    else
        pg_restore --list "$DB_FILE" >/dev/null
    fi
fi

log "Validating attachment backup: $ATTACHMENTS_FILE"
if [ "$DRY_RUN" = "1" ]; then
    log "DRY RUN: tar -tzf $ATTACHMENTS_FILE >/dev/null"
else
    tar -tzf "$ATTACHMENTS_FILE" >/dev/null
fi

log "Restore smoke test passed."
