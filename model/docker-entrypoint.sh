#!/bin/sh
set -eu

role="${1:-api}"

case "$role" in
  api)
    exec python -m uvicorn ssri_model.api.app:app --host 0.0.0.0 --port "${SSRI_API_PORT:-8000}"
    ;;
  worker)
    exec python -m celery -A ssri_model.worker.celery_app worker \
      --loglevel="${LOG_LEVEL:-info}" \
      -Q ssri_jobs \
      --concurrency="${SSRI_CELERY_CONCURRENCY:-1}"
    ;;
  recovery)
    exec python -m ssri_model.infrastructure.recovery --loop
    ;;
  recovery-once)
    exec python -m ssri_model.infrastructure.recovery --once
    ;;
  *)
    exec "$@"
    ;;
esac
