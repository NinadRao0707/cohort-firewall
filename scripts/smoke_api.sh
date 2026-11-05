#!/usr/bin/env bash
# First real test of the FastAPI layer. Start the API first:  uvicorn api.main:app --reload
# Then, from the repo root:  bash scripts/smoke_api.sh
set -euo pipefail
API="${API:-http://localhost:8000}"
V=data/variants
[ -f "$V/manifest.json" ] || python data/make_variants.py

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; exit 1; }

has() { grep -q "$2" <<<"$1"; }  # avoids pipe/SIGPIPE issues under pipefail

r=$(curl -sf "$API/health" || true); has "$r" '"ok":true' && pass "health" || fail "health (is the API running?)"

for case in clean phi no_dictionary prompt_injection q2_clinical; do
  expected=$(python3 -c "import json;print({c['case']:c['expected_verdict'] for c in json.load(open('$V/manifest.json'))}['$case'])")
  args=(-F "dataset=@$V/$case/data.csv" -F "spec=<$V/$case/spec.json")
  [ -f "$V/$case/dictionary.json" ] && args+=(-F "dictionary=@$V/$case/dictionary.json")
  curl -sf -X POST "$API/evaluate" "${args[@]}" -o "/tmp/cf_$case.json" || fail "evaluate $case (HTTP error)"
  got=$(python3 -c "import json;print(json.load(open('/tmp/cf_$case.json'))['verdict'])")
  [ "$got" = "$expected" ] && pass "evaluate $case -> $got" || fail "evaluate $case expected $expected got $got"
done

python3 -c "import json;print(json.dumps({'certificate':json.load(open('/tmp/cf_clean.json'))['certificate']}))" > /tmp/cf_cert.json
r=$(curl -sf -X POST "$API/verify" -H 'Content-Type: application/json' -d @/tmp/cf_cert.json || true)
has "$r" '"valid":true' && pass "verify genuine certificate" || fail "verify genuine certificate"
python3 -c "import json;d=json.load(open('/tmp/cf_cert.json'));d['certificate']['payload']['verdict']='BLOCKED';print(json.dumps(d))" > /tmp/cf_cert_bad.json
r=$(curl -sf -X POST "$API/verify" -H 'Content-Type: application/json' -d @/tmp/cf_cert_bad.json || true)
has "$r" '"valid":false' && pass "reject tampered certificate" || fail "reject tampered certificate"

r=$(curl -sf "$API/policy" || true); has "$r" 'PHI-001' && pass "policy endpoint" || fail "policy endpoint"
echo "All API smoke tests passed."
