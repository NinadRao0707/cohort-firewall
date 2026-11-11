#!/usr/bin/env bash
# Build each rehearsal release with the event's make_release.py, run the Control Tower, then grade.
# Run from the cohort-firewall repo root with the venv active.
set -uo pipefail
CH="${CF_CHALLENGE_REPO:-$HOME/oncosys-hackathon-challenge}"
mkdir -p outputs
status=0
for cfg in rehearsal/rehearsal-*.json; do
  name=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['name'])" "$cfg")
  echo "================ $name"
  (cd "$CH" && python data/tcga-brca/make_release.py --config "$OLDPWD/$cfg") || { status=1; continue; }
  python -m cohort_firewall.tower --challenge-repo "$CH" --b "$CH/data/tcga-brca/releases/$name" \
    --out "outputs/findings-$name.json" > "outputs/tower-$name.log" || { echo "tower failed, see outputs/tower-$name.log"; status=1; continue; }
  python "$CH/format/validate.py" "outputs/findings-$name.json" || status=1
  python scripts/grade_tower.py "outputs/findings-$name.json" "$CH/data/tcga-brca/releases/$name/CHANGES.json" || status=1
done
exit $status
