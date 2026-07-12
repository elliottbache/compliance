#!/usr/bin/env bash

set -euo pipefail

DEFAULT_COMPOSE_FILE="docker-compose.prod.yaml"
DEFAULT_ENV_FILE="/etc/compliance/.env"
DEFAULT_DB_BACKUP_DIR="/var/backups/compliance/db"
DEFAULT_ATTACHMENTS_BACKUP_DIR="/var/backups/compliance/attachments"
DEFAULT_DEPLOYMENT_ATTACHMENTS_DIR="/var/lib/compliance/attachments"

timestamp() {
    date -u +"%Y%m%dT%H%M%SZ"
}

log() {
    printf '%s\n' "$*" >&2
}

die() {
    log "ERROR: $*"
    exit 1
}

usage_common_modes() {
    cat <<'EOF'
Common options:
  --mode docker|host      Runtime mode. Defaults to docker.
  --env-file PATH         Environment file. Defaults to /etc/compliance/.env.
  --dry-run               Print actions without running them.
  -h, --help              Show help.
EOF
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_file() {
    [ -f "$1" ] || die "File does not exist: $1"
}

require_dir() {
    [ -d "$1" ] || die "Directory does not exist: $1"
}

ensure_dir() {
    if [ "${DRY_RUN:-0}" = "1" ]; then
        log "DRY RUN: mkdir -p $1"
    else
        mkdir -p "$1"
    fi
}

run_cmd() {
    if [ "${DRY_RUN:-0}" = "1" ]; then
        log "DRY RUN: $*"
    else
        "$@"
    fi
}

load_env_file() {
    local env_file="$1"
    require_file "$env_file"
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
}

strip_env_var_cr() {
    local name="$1"
    if [ -n "${!name:-}" ]; then
        printf -v "$name" '%s' "${!name//$'\r'/}"
    fi
}

require_env_var() {
    local name="$1"
    if [ -z "${!name:-}" ]; then
        die "Required environment variable is missing: $name"
    fi
}

require_db_env() {
    strip_env_var_cr POSTGRES_USER
    strip_env_var_cr POSTGRES_PASSWORD
    strip_env_var_cr POSTGRES_DB
    strip_env_var_cr POSTGRES_HOST
    strip_env_var_cr POSTGRES_PORT
    require_env_var POSTGRES_USER
    require_env_var POSTGRES_PASSWORD
    require_env_var POSTGRES_DB
    require_env_var POSTGRES_HOST
    POSTGRES_PORT="${POSTGRES_PORT:-5432}"
}
