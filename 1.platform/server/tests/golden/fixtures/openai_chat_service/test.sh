#!/usr/bin/env bash
# Run the fixture test suite. No network and no API key required.
cd "$(dirname "$0")"
exec "${PYTHON:-python}" -m pytest -q
