#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$ROOT_DIR/agent"
OUT_DIR="$AGENT_DIR/bin"
CACHE_DIR="${GOCACHE:-$ROOT_DIR/.cache/go-build}"

mkdir -p "$OUT_DIR"
mkdir -p "$CACHE_DIR"

for arch in amd64 arm64; do
  echo "Building linux-$arch agent"
  (
    cd "$AGENT_DIR"
    GOOS=linux GOARCH="$arch" GOCACHE="$CACHE_DIR" go build \
      -o "$OUT_DIR/vulnflanker-agent-linux-$arch" \
      ./cmd/vulnflanker-agent
  )
done

echo "Agent artifacts written to $OUT_DIR"
