#!/usr/bin/env bash
# Run the fixture test suite. Exits non-zero while the bug is unfixed.
cd "$(dirname "$0")"
exec "${PYTHON:-python}" -m pytest -q
