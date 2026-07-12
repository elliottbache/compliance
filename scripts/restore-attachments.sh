#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

MODE="docker"
ENV_FILE="$DEFAULT_ENV_FILE"
TARGET_ATTACHMENTS_DIR=""
BACKUP_FILE=""
CONFIRM_RESTORE=0
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 --file BACKUP.tar.gz --confirm-restore [options]

Restore a compressed attachment backup.

The current attachment directory is moved to a timestamped pre-restore path
before the archive is extracted.

Options:
  --file PATH             Attachment archive created by backup-attachments.sh.
  --confirm-restore       Required. Confirms destructive attachment restore.
  --attachments-dir PATH  Host attachment directory to restore.
$(usage_common_modes)

Examples:
  $0 --file /var/backups/compliance/attachments/compliance-attachments-20260101T120000Z.tar.gz --confirm-restore
  $0 --mode host --env-file backend/.env --file /tmp/attachments.tar.gz --confirm-restore
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
        --attachments-dir)
            TARGET_ATTACHMENTS_DIR="${2:-}"
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

if [ -z "$TARGET_ATTACHMENTS_DIR" ]; then
    if [ "$MODE" = "docker" ]; then
        TARGET_ATTACHMENTS_DIR="$DEFAULT_DEPLOYMENT_ATTACHMENTS_DIR"
    else
        strip_env_var_cr ATTACHMENTS_DIR
        require_env_var ATTACHMENTS_DIR
        TARGET_ATTACHMENTS_DIR="${ATTACHMENTS_DIR/#\~/$HOME}"
    fi
fi

PARENT_DIR="$(dirname "$TARGET_ATTACHMENTS_DIR")"
PRE_RESTORE_DIR="$TARGET_ATTACHMENTS_DIR.pre-restore.$(timestamp)"

if [ "$DRY_RUN" = "1" ]; then
    if [ -d "$TARGET_ATTACHMENTS_DIR" ]; then
        log "DRY RUN: mv $TARGET_ATTACHMENTS_DIR $PRE_RESTORE_DIR"
    fi
    log "DRY RUN: mkdir -p $TARGET_ATTACHMENTS_DIR"
    log "DRY RUN: tar -xzf $BACKUP_FILE -C $TARGET_ATTACHMENTS_DIR"
else
    mkdir -p "$PARENT_DIR"
    if [ -e "$TARGET_ATTACHMENTS_DIR" ]; then
        mv "$TARGET_ATTACHMENTS_DIR" "$PRE_RESTORE_DIR"
        log "Moved existing attachments to: $PRE_RESTORE_DIR"
    fi
    mkdir -p "$TARGET_ATTACHMENTS_DIR"
    tar -xzf "$BACKUP_FILE" -C "$TARGET_ATTACHMENTS_DIR"
fi

log "Attachments restored from: $BACKUP_FILE"
