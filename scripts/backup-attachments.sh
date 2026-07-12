#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/backup-common.sh
. "$SCRIPT_DIR/lib/backup-common.sh"

MODE="docker"
ENV_FILE="$DEFAULT_ENV_FILE"
TARGET_ATTACHMENTS_DIR=""
OUTPUT_DIR="$DEFAULT_ATTACHMENTS_BACKUP_DIR"
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $0 [options]

Create a compressed tar backup of the attachment storage directory.

Options:
  --attachments-dir PATH  Host attachment directory to back up.
  --output-dir PATH       Backup output directory. Defaults to $DEFAULT_ATTACHMENTS_BACKUP_DIR.
$(usage_common_modes)

Examples:
  $0
  $0 --mode host --env-file backend/.env --attachments-dir ~/.local/share/compliance/attachments --output-dir /tmp
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

if [ -z "$TARGET_ATTACHMENTS_DIR" ]; then
    if [ "$MODE" = "docker" ]; then
        TARGET_ATTACHMENTS_DIR="$DEFAULT_DEPLOYMENT_ATTACHMENTS_DIR"
    else
        strip_env_var_cr ATTACHMENTS_DIR
        require_env_var ATTACHMENTS_DIR
        TARGET_ATTACHMENTS_DIR="${ATTACHMENTS_DIR/#\~/$HOME}"
    fi
fi

require_dir "$TARGET_ATTACHMENTS_DIR"
ensure_dir "$OUTPUT_DIR"

BACKUP_FILE="$OUTPUT_DIR/compliance-attachments-$(timestamp).tar.gz"

if [ "$DRY_RUN" = "1" ]; then
    log "DRY RUN: tar -C $TARGET_ATTACHMENTS_DIR -czf $BACKUP_FILE ."
else
    tar -C "$TARGET_ATTACHMENTS_DIR" -czf "$BACKUP_FILE" .
fi

log "Attachment backup written to: $BACKUP_FILE"
