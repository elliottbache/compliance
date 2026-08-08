#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

DB_DIR="$DEFAULT_DB_BACKUP_DIR"
ATTACHMENTS_DIR="$DEFAULT_ATTACHMENTS_BACKUP_DIR"
KEEP_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 [options]

Delete database and attachment backups older than the retention window.

Options:
  --db-dir PATH           Database backup directory. Defaults to $DEFAULT_DB_BACKUP_DIR.
  --attachments-dir PATH  Attachment backup directory. Defaults to $DEFAULT_ATTACHMENTS_BACKUP_DIR.
  --keep-days DAYS        Number of days to retain. Defaults to $KEEP_DAYS.
  --dry-run               Print files that would be deleted.
  -h, --help              Show help.

Examples:
  $0
  $0 --keep-days 60 --dry-run
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --db-dir)
            DB_DIR="${2:-}"
            shift 2
            ;;
        --attachments-dir)
            ATTACHMENTS_DIR="${2:-}"
            shift 2
            ;;
        --keep-days)
            KEEP_DAYS="${2:-}"
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

case "$KEEP_DAYS" in
    ''|*[!0-9]*)
        die "--keep-days must be a positive integer"
        ;;
esac
[ "$KEEP_DAYS" -gt 0 ] || die "--keep-days must be greater than zero"

require_dir "$DB_DIR"
require_dir "$ATTACHMENTS_DIR"

prune_dir() {
    local dir="$1"
    local pattern="$2"

    if [ "$DRY_RUN" = "1" ]; then
        find "$dir" -type f -name "$pattern" -mtime +"$KEEP_DAYS" -print
    else
        find "$dir" -type f -name "$pattern" -mtime +"$KEEP_DAYS" -print -delete
    fi
}

log "Pruning database backups older than $KEEP_DAYS days from: $DB_DIR"
prune_dir "$DB_DIR" "compliance-db-*.dump"

log "Pruning attachment backups older than $KEEP_DAYS days from: $ATTACHMENTS_DIR"
prune_dir "$ATTACHMENTS_DIR" "compliance-attachments-*.tar.gz"
