#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "${ROOT_DIR}"
require_env_file

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"

exec "${PYTHON_BIN}" -m uvicorn app.main_agent:app --reload --host "${HOST}" --port "${PORT}"
