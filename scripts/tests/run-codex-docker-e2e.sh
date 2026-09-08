#!/usr/bin/env bash
# Run the real Codex installer lifecycle in a disposable Linux container.
set -euo pipefail

SOURCE_DIR="${1:-.}"
SOURCE_DIR=$(cd "$SOURCE_DIR" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$SOURCE_DIR/scripts/tests/docker_e2e.py" --source-dir "$SOURCE_DIR"
