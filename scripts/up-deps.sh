#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "${ROOT_DIR}"

compose -f "${ROOT_DIR}/deploy/docker-compose.yml" up -d postgres redis

