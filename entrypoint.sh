#!/usr/bin/env sh
set -e

MODULE=${APP_MODULE:-app.main:app}
PORT=${PORT:-8000}

exec uvicorn "$MODULE" --host 0.0.0.0 --port "$PORT"
