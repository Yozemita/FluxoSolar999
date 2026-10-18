#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-access-log
