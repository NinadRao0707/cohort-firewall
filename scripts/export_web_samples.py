"""Regenerate the web app's sample results on THIS machine, signed with THIS machine's key.

The samples shipped in web/public/samples were signed with a different (build) key, so
"Verify signature" on them would wrongly report a mismatch. Run this once after setup and
again whenever the engine or rules change.

  python scripts/export_web_samples.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cohort_firewall.engine import evaluate_dataset  # noqa: E402

OUT = ROOT / "web" / "public" / "samples"
VARIANTS = ROOT / "data" / "variants"
CASES = ["clean", "q3_survival", "q2_clinical", "leakage", "skewed_subgroup", "phi",
         "prompt_injection", "no_dictionary"]
SYNTHEA = {"synthea_small": ROOT / "data" / "synthea", "synthea_large": ROOT / "data" / "synthea_large"}


def write(name, result):
    (OUT / f"{name}.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"{name:45s} {result['verdict']}")


OUT.mkdir(parents=True, exist_ok=True)
if not (VARIANTS / "manifest.json").exists():
    sys.exit("Run python data/make_variants.py first.")
for case in CASES:
    f = VARIANTS / case
    dct = f / "dictionary.json"
    write(case, evaluate_dataset((f / "data.csv").read_bytes(),
                                 json.loads(dct.read_text()) if dct.exists() else None,
                                 spec=json.loads((f / "spec.json").read_text())))

for label, folder in SYNTHEA.items():
    data, dct = folder / "breast_cohort.csv", folder / "breast_cohort.dictionary.json"
    if not data.exists():
        print(f"skip {label}: {data} not found")
        continue
    for spec in ["synthea_q1_progression_2yr", "synthea_q2_survival_5yr"]:
        s = json.loads((ROOT / "examples" / "specs" / f"{spec}.json").read_text())
        write(f"{label}_{spec.removeprefix('synthea_')}",
              evaluate_dataset(data.read_bytes(), json.loads(dct.read_text()), spec=s))
