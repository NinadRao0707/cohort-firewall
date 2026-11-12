#!/usr/bin/env bash
# One-command setup from a fresh clone. Run from the cohort-firewall folder:
#   bash scripts/setup.sh
# Uses an existing challenge repo at $CF_CHALLENGE_REPO (default ../oncosys-hackathon-challenge),
# or clones it there. Safe to run again: every step skips work that is already done.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
CH="${CF_CHALLENGE_REPO:-$ROOT/../oncosys-hackathon-challenge}"
step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nSETUP FAILED: %s\n' "$1"; exit 1; }

step "Checking tools"
command -v python3 >/dev/null || fail "python3 not found. Install Python 3.10 or newer."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || fail "Python 3.10 or newer is required (found $(python3 --version))."
command -v git >/dev/null || fail "git not found."
if command -v node >/dev/null; then
  echo "python $(python3 --version | cut -d' ' -f2), node $(node --version)"
  major=$(node --version | sed 's/^v//; s/\..*//')
  [ "$major" -ge 20 ] || echo "Warning: Node $(node --version) is old; the web app's Next.js may need a newer Node."
else
  echo "Warning: node not found. The command-line tool will work; the web app needs Node.js."
fi

step "Python environment"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
export SSL_CERT_FILE="$(python -m certifi)"   # fixes CERTIFICATE_VERIFY_FAILED on python.org macOS installs

step "Challenge repo and frozen TCGA-BRCA data"
if [ ! -d "$CH/.git" ] && [ ! -f "$CH/data/tcga-brca/fetch.py" ]; then
  git clone https://github.com/disleveK/oncosys-hackathon-challenge.git "$CH"
fi
CH="$(cd "$CH" && pwd)"
(cd "$CH" && python data/tcga-brca/fetch.py) || fail "fetch.py failed. See its message above."
(cd "$CH" && [ -d data/tcga-brca/releases/practice-B ] || python data/tcga-brca/make_release.py)
(cd "$CH" && python data/tcga-brca/make_release.py --verify) || fail "practice-B does not match the published release."

step "Test data, readiness table and saved samples"
python data/make_variants.py >/dev/null
python data/flatten_tcga.py --challenge-repo "$CH" | sed -n '1,4p'
CF_CHALLENGE_REPO="$CH" python scripts/export_web_samples.py >/dev/null
echo "samples written to web/public/samples/"

step "Quick tests"
python tests/test_variants.py >/dev/null && echo "readiness cases: pass" || fail "readiness tests failed (python tests/test_variants.py)"
python tests/test_review.py >/dev/null && echo "review rules: pass" || fail "review tests failed (python tests/test_review.py)"
CF_CHALLENGE_REPO="$CH" python tests/test_tower.py >/dev/null && echo "Control Tower scenarios: pass" || fail "tower tests failed (python tests/test_tower.py)"

if command -v npm >/dev/null; then
  step "Web app"
  (cd web && npm install --silent) || fail "npm install failed in web/."
  [ -f web/.env.local ] || cp web/.env.local.example web/.env.local
  echo "web dependencies installed"
fi

printf '\nSetup complete.\n'
printf 'Challenge repo: %s\n' "$CH"
printf 'Start everything:   bash scripts/run.sh\n'
printf 'Command line only:  source .venv/bin/activate && python -m cohort_firewall.tower --challenge-repo "%s" --b "%s/data/tcga-brca/releases/practice-B" --out outputs/findings-practice-B.json\n' "$CH" "$CH"
