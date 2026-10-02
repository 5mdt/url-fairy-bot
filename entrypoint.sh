#!/usr/bin/env sh
# #BUG-0043: start as root only to fix volume ownership, then drop to `app`.
set -eu

umask 022 # cached files stay world-readable for nginx / telegram-bot-api

APP_USER=app
APP_UID=1000
for dir in "${CACHE_DIR:-/tmp/url-fairy-bot-cache/}" "${COOKIES_DIR:-/config/}"; do
    mkdir -p "$dir"
    # One-time fix for volumes created by earlier root-running versions.
    if [ "$(stat -c %u "$dir")" != "$APP_UID" ]; then
        chown -R "$APP_USER" "$dir" || echo "warning: cannot chown $dir" >&2
    fi
done

exec su-exec "$APP_USER" /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
