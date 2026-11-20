#!/usr/bin/env bash
# One-command start for macOS / Linux: creates a virtualenv, installs deps, starts the app.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "Creating virtual environment…"
  "$PY" -m venv .venv
fi
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
echo "Starting HousingSearch on http://localhost:${HS_PORT:-8000}"
exec ./.venv/bin/python -m housingsearch serve "$@"
