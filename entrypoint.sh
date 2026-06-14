#!/usr/bin/env sh

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
