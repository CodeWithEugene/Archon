#!/usr/bin/env bash
# Install the fixture in editable mode plus its test runner.
set -euo pipefail
cd "$(dirname "$0")"
"${PYTHON:-python}" -m pip install -e . pytest
