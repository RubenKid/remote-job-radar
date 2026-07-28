#!/usr/bin/env bash
# Launch the Remote Job Radar web app locally.
# Usage:  ./run.sh            (starts the web server on http://localhost:8000)
#         PORT=9000 ./run.sh  (custom port)
#         ./run.sh worker     (run the daily digest for all users once, then exit)
set -euo pipefail

cd "$(dirname "$0")"
VENV=".venv"
PY="$VENV/bin/python"

# 1. Create the virtualenv if it doesn't exist yet.
if [ ! -x "$PY" ]; then
  echo "→ Creating virtualenv in $VENV ..."
  python3 -m venv "$VENV"
fi

# 2. Install/refresh dependencies if anything is missing.
if ! "$PY" -c "import job_radar.web, anthropic" >/dev/null 2>&1; then
  echo "→ Installing dependencies (web + anthropic extras) ..."
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e '.[web,anthropic]'
fi

# 3. Warn if .env is missing (the app still runs with dev login).
if [ ! -f .env ]; then
  echo "⚠  No .env found — copy .env.example to .env and fill it in."
fi

# 4. Run.
if [ "${1:-}" = "worker" ]; then
  echo "→ Running the daily digest worker ..."
  exec "$PY" -m job_radar.web.worker
fi

echo "→ Web app: http://localhost:${PORT:-8000}   (Ctrl+C to stop)"
exec "$PY" -m job_radar.web
