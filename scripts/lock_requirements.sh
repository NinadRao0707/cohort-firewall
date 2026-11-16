#!/usr/bin/env bash
# Pin the exact Python package versions from a working environment, so a rerun next month
# produces the same numbers you signed today. Run inside the project's venv after the tests pass:
#   bash scripts/lock_requirements.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -n "${VIRTUAL_ENV:-}" ] || { echo "Activate the venv first: source .venv/bin/activate"; exit 1; }
{
  echo "# Exact versions from a verified environment ($(python --version 2>&1), $(uname -s))."
  echo "# Made by scripts/lock_requirements.sh on $(date -u +%Y-%m-%d). setup.sh installs this file when present."
  pip freeze --exclude-editable | grep -v -E "^(-e |pip==|setuptools==|wheel==)"
} > requirements.lock
echo "Wrote requirements.lock ($(grep -vc '^#' requirements.lock) packages). Commit it with: git add requirements.lock"
