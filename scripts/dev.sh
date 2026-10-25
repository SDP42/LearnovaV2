#!/usr/bin/env bash
# One command to run the MVP: API on :8000 and the web app on :5173.
#   ./scripts/dev.sh        (Ctrl-C stops both)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
[ -d frontend/node_modules ] || (cd frontend && npm install)
python3 -m uvicorn apps.api.main:app --port 8000 --reload & API=$!
trap 'kill $API 2>/dev/null' EXIT
cd frontend && npm run dev
