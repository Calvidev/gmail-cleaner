#!/usr/bin/env bash
# Arranca Fantasy Tool. Crea el entorno virtual la primera vez.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creando el entorno virtual…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

PORT="${PORT:-8000}"
echo "Fantasy Tool en http://127.0.0.1:${PORT}"
exec ./.venv/bin/python -m uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT}" "$@"
