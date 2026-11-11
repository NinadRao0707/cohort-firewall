"""Run the readiness firewall on the flattened TCGA-BRCA table for every TCGA question spec.

  python data/flatten_tcga.py --challenge-repo ~/oncosys-hackathon-challenge
  python scripts/run_tcga_specs.py                       # uses data/tcga/tcga_brca_raw.csv
  python scripts/run_tcga_specs.py --stem tcga_brca_practice-B
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cohort_firewall.engine import evaluate_dataset  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dir", type=Path, default=ROOT / "data" / "tcga")
ap.add_argument("--stem", default="tcga_brca_raw")
ap.add_argument("--save", type=Path, help="also write each full result as JSON into this folder")
a = ap.parse_args()
data_path, dict_path = a.dir / f"{a.stem}.csv", a.dir / f"{a.stem}.dictionary.json"
if not data_path.exists():
    sys.exit(f"Missing {data_path}. Run data/flatten_tcga.py first.")
data, dictionary = data_path.read_bytes(), json.loads(dict_path.read_text())
if a.save:
    a.save.mkdir(parents=True, exist_ok=True)
for spec_path in sorted((ROOT / "examples" / "specs").glob("tcga_*.json")):
    out = evaluate_dataset(data, dictionary, spec=json.loads(spec_path.read_text()))
    m = {c["check"]: c["metrics"] for c in out["checks"]}
    print("=" * 78)
    print(f"{spec_path.stem}: {out['verdict']}   (human review {out['human_review']['level']})")
    print(f"  cohort n={m.get('cohort', {}).get('n_cohort')}  events={m.get('outcome_events', {}).get('n_events')}  "
          f"EPP={m.get('outcome_events', {}).get('events_per_parameter')}  "
          f"horizon coverage={m.get('temporal', {}).get('horizon_coverage')}  "
          f"worst missing={m.get('completeness', {}).get('worst_feature')} ({m.get('completeness', {}).get('max_feature_missing_rate')})")
    for f in out["findings"]:
        print(f"  [{f['rule_id']}] {f['verdict']}: {f['reason']}")
    for n in out.get("notes", []):
        print(f"  note: {n}")
    if a.save:
        (a.save / f"{spec_path.stem}.json").write_text(json.dumps(out, indent=2, default=str))
