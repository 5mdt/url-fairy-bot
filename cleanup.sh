#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Config
# -----------------------------
LOG_LEVEL="${LOG_LEVEL:-INFO}"
DRY_RUN=0

# -----------------------------
# Logging
# -----------------------------
log_level_allowed() {
  case "$LOG_LEVEL" in
    DEBUG) return 0 ;;
    INFO)  [[ "$1" != "DEBUG" ]] ;;
    WARN)  [[ "$1" == "WARN" || "$1" == "ERROR" ]] ;;
    ERROR) [[ "$1" == "ERROR" ]] ;;
    *) return 1 ;;
  esac
}

log() {
  local level="$1"
  shift

  log_level_allowed "$level" || return 0
  printf '[%s] [%s] %s\n' "$(date -Iseconds)" "$level" "$*" >&2
}

die() {
  log "ERROR" "$*"
  exit 1
}

# -----------------------------
# Helpers (DRY / Fail-fast)
# -----------------------------
require_env() {
  local var="$1"
  [[ -n "${!var:-}" ]] || die "$var is not set"
}

is_numeric() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

# -----------------------------
# Help
# -----------------------------
show_help() {
  cat <<EOF
Usage:
  $(basename "$0") [--once|--serve] [--dry-run]

Modes:
  --once        Run cleanup once (default)
  --serve       Run continuously

Options:
  --dry-run     Show deletions without removing files
  -h, --help    Show help

Environment:
  CACHE_DIR      Required
  FILE_TTL       Required (seconds)
  CRON_INTERVAL  Required for --serve
  LOG_LEVEL      INFO|DEBUG|WARN|ERROR (default: INFO)
EOF
}

# -----------------------------
# Environment validation
# -----------------------------
check_env() {
  require_env CACHE_DIR
  require_env FILE_TTL

  is_numeric "$FILE_TTL" || die "FILE_TTL must be numeric"

  [[ -d "$CACHE_DIR" && -w "$CACHE_DIR" ]] \
    || die "CACHE_DIR must be writable: $CACHE_DIR"

  [[ "$CACHE_DIR" != "/" ]] || die "CACHE_DIR cannot be root"

  log "INFO" "Environment validated"
}

wait_for_cache_dir() {
  local timeout=10 interval=1 elapsed=0

  while (( elapsed < timeout )); do
    [[ -d "$CACHE_DIR" && -w "$CACHE_DIR" ]] && {
      log "INFO" "CACHE_DIR ready: $CACHE_DIR"
      return 0
    }

    sleep "$interval"
    (( elapsed += interval ))
  done

  die "CACHE_DIR not available after ${timeout}s"
}

log_env() {
  log "INFO" "=== Runtime Environment ==="
  log "INFO" "Script        : $(basename "$0")"
  log "INFO" "PID           : $$"
  log "INFO" "User          : $(id -un 2>/dev/null || echo unknown)"
  log "INFO" "CACHE_DIR     : ${CACHE_DIR:-unset}"
  log "INFO" "FILE_TTL      : ${FILE_TTL:-unset}"
  log "INFO" "CRON_INTERVAL : ${CRON_INTERVAL:-unset}"
  log "INFO" "LOG_LEVEL     : $LOG_LEVEL"
  log "INFO" "DRY_RUN       : $DRY_RUN"
  log "INFO" "==========================="
}

# -----------------------------
# Core logic
# -----------------------------
cleanup() {
  local days
  days=$(( FILE_TTL / 86400 ))
  (( days < 1 )) && days=1

  log "INFO" "Cleaning files older than ${days} days"

  while IFS= read -r -d '' f; do
    if (( DRY_RUN )); then
      log "INFO" "[dry-run] $f"
      continue
    fi

    rm -f -- "$f" \
      && log "DEBUG" "Deleted: $f" \
      || log "WARN" "Failed: $f"

  done < <(
    find "$CACHE_DIR" -type f -mtime +"$days" -print0 2>/dev/null
  )

  if (( DRY_RUN )); then
    log "INFO" "[dry-run] remove empty directories"
  else
    find "$CACHE_DIR" -type d -empty -delete 2>/dev/null || true
  fi
}

run_once() {
  cleanup
}

run_serve() {
  require_env CRON_INTERVAL
  is_numeric "$CRON_INTERVAL" || die "CRON_INTERVAL must be numeric"

  while true; do
    cleanup
    sleep "$CRON_INTERVAL" || break
  done
}

# -----------------------------
# Args
# -----------------------------
parse_args() {
  MODE="once"

  [[ $# -eq 0 ]] && {
    show_help
    exit 0
  }

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --once) MODE="once" ;;
      --serve) MODE="serve" ;;
      --dry-run) DRY_RUN=1 ;;
      -h|--help) show_help; exit 0 ;;
      *) die "Unknown argument: $1" ;;
    esac
    shift
  done
}

# -----------------------------
# Main
# -----------------------------
main() {
  parse_args "$@"
  log_env
  check_env
  wait_for_cache_dir

  log "INFO" "Started cache cleaner (mode=$MODE, dry_run=$DRY_RUN)"

  trap 'log "INFO" "Stopping (signal)"; exit 0' INT TERM

  [[ "$MODE" == "serve" ]] && run_serve || run_once

  log "INFO" "Exited"
}

# -----------------------------
# Entry point
# -----------------------------
[[ "${BASH_SOURCE[0]}" == "$0" ]] && main "$@"
