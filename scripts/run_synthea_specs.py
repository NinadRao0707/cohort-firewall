"""Run the firewall on the flattened Synthea cohort for each Synthea question spec.

Run from the repo root after flattening:
  python data/flatten_synthea.py --synthea-dir ~/synthea/output_full/csv --cancer breast --out data/synthea
  python scripts/run_synthea_specs.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cohort_firewall.engine import evaluate_dataset  # noqa: E402

DATA = ROOT / "data" / "synthea" / "breast_cohort.csv"
DICT = ROOT / "data" / "synthea" / "breast_cohort.dictionary.json"
if not DATA.exists():
    sys.exit(f"Missing {DATA}. Run the flatten command in this file's docstring first.")

data, dictionary = DATA.read_bytes(), json.loads(DICT.read_text())
for spec_path in sorted((ROOT / "examples" / "specs").glob("synthea_*.json")):
    out = evaluate_dataset(data, dictionary, spec=json.loads(spec_path.read_text()))
    m = {c["check"]: c["metrics"] for c in out["checks"]}
    print("=" * 78)
    print(f"{spec_path.stem}: {out['verdict']}")
    print(f"cohort n={m.get('cohort', {}).get('n_cohort')}  "
          f"events={m.get('outcome_events', {}).get('n_events')}  "
          f"EPP={m.get('outcome_events', {}).get('events_per_parameter')}  "
          f"worst missing={m.get('completeness', {}).get('worst_feature')} "
          f"({m.get('completeness', {}).get('max_feature_missing_rate')})")
    for f in out["findings"]:
        print(f"  [{f['rule_id']}] {f['verdict']}: {f['reason']}")
