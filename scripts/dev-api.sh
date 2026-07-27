#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "${ROOT_DIR}"
require_env_file

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec "${PYTHON_BIN}" -m uvicorn app.main:app --reload --host "${HOST}" --port "${PORT}"

