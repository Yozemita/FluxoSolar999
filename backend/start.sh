#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Railway executes this shell script so PORT is expanded before Uvicorn starts.
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-access-log
