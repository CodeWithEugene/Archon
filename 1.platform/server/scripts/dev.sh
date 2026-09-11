#!/usr/bin/env bash
# Development server with offline backends. Real keys in .env override these defaults.
set -euo pipefail
cd "$(dirname "$0")/.."
export ARCHON_LLM_BACKEND="${ARCHON_LLM_BACKEND:-fake}"
export ARCHON_SANDBOX_BACKEND="${ARCHON_SANDBOX_BACKEND:-fake}"
export ARCHON_DB_PATH="${ARCHON_DB_PATH:-/tmp/archon-dev.db}"
export ARCHON_RECORDINGS_DIR="${ARCHON_RECORDINGS_DIR:-./tests/golden/recordings}"
exec .venv/bin/uvicorn app.main:app --port "${PORT:-8010}" --reload
