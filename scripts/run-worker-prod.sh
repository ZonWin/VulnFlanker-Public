#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "${ROOT_DIR}"
require_env_file

LOG_LEVEL="${LOG_LEVEL:-INFO}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"

exec "${PYTHON_BIN}" -m celery -A app.workers.celery_app:celery_app worker --loglevel="${LOG_LEVEL}" --concurrency="${CELERY_CONCURRENCY}"

