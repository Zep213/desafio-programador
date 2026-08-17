#!/bin/sh
set -e

mkdir -p /app/data
chown -R appuser:appuser /app/data

exec su -s /bin/sh appuser -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
