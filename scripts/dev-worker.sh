#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "${ROOT_DIR}"
require_env_file

LOG_LEVEL="${LOG_LEVEL:-INFO}"
CELERY_POOL="${CELERY_POOL:-prefork}"

exec "${PYTHON_BIN}" -m celery -A app.workers.celery_app:celery_app worker --pool="${CELERY_POOL}" --loglevel="${LOG_LEVEL}"

