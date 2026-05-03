#!/usr/bin/env bash
# Convenience launcher: creates the venv on first run, installs deps,
# then starts the Flask server.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[run] creating virtualenv at .venv"
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f .venv/.deps_installed ] || [ requirements.txt -nt .venv/.deps_installed ]; then
  echo "[run] installing dependencies"
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
  touch .venv/.deps_installed
fi

if [ -f .env ]; then
  echo "[run] loading .env"
  set -a; source .env; set +a
fi

echo "[run] starting Flask on http://localhost:${PORT:-5050}"
exec python app.py
