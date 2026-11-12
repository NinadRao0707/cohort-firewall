#!/usr/bin/env bash
# Rehearse what a judge or the paired team does: clone the repo into an empty folder, follow setup,
# run the tests and one real comparison. Reuses your existing challenge repo so data isn't re-downloaded.
#   bash scripts/fresh_clone_test.sh [repo-url]
set -euo pipefail
URL="${1:-https://github.com/NinadRao0707/cohort-firewall.git}"
CH="${CF_CHALLENGE_REPO:-$HOME/oncosys-hackathon-challenge}"
DIR="$(mktemp -d)/cohort-firewall"
echo "Cloning $URL into $DIR"
git clone -q "$URL" "$DIR"
cd "$DIR"
CF_CHALLENGE_REPO="$CH" bash scripts/setup.sh
source .venv/bin/activate
python -m cohort_firewall.tower --challenge-repo "$CH" --b "$CH/data/tcga-brca/releases/practice-B" --out outputs/f.json | tail -1
python "$CH/format/validate.py" outputs/f.json
python scripts/grade_tower.py outputs/f.json "$CH/data/tcga-brca/releases/practice-B/CHANGES.json" | head -1
if command -v npm >/dev/null; then (cd web && npm run build >/dev/null && echo "web build: pass"); fi
echo "FRESH CLONE TEST PASSED in $DIR"
