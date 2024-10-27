#!/usr/bin/env bash

poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
