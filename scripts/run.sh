#!/usr/bin/env bash
# Start the API and the web app together. Ctrl+C stops both.
#   bash scripts/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export CF_CHALLENGE_REPO="${CF_CHALLENGE_REPO:-$ROOT/../oncosys-hackathon-challenge}"
[ -d .venv ] || { echo "Run bash scripts/setup.sh first."; exit 1; }
# shellcheck disable=SC1091
source .venv/bin/activate
mkdir -p outputs
uvicorn api.main:app --port 8000 > outputs/api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 30); do
  curl -sf http://localhost:8000/health >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sf http://localhost:8000/health >/dev/null 2>&1 || { echo "API did not start; see outputs/api.log"; exit 1; }
echo "API running on http://localhost:8000 (log: outputs/api.log)"
echo "Open http://localhost:3000/tower (Release check) or http://localhost:3000 (Question check)"
cd web && npm run dev
