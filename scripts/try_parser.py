"""Try the Claude question parser against the demo cohort's dictionary.

Needs: pip install anthropic ; export ANTHROPIC_API_KEY=... (optionally CF_MODEL=<model id>)
Run from the repo root:  python scripts/try_parser.py
Each question prints the parsed spec, whether it passed validation, and the resulting verdict.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cohort_firewall.engine import evaluate_dataset  # noqa: E402
from cohort_firewall.llm import parse_question  # noqa: E402
from cohort_firewall.spec import SpecError, spec_from_dict  # noqa: E402

DEMO = ROOT / "data" / "demo"
data = (DEMO / "breast_cohort.csv").read_bytes()
dictionary = json.loads((DEMO / "breast_cohort.dictionary.json").read_text())
columns = list(dictionary["columns"])

QUESTIONS = [  # expected verdict in brackets
    "[Ready] Build a research model for 2-year recurrence in breast cancer patients diagnosed since 2012 "
    "using stage, ER, PR, HER2, tumor size, positive nodes and age, and check performance across race and ethnicity.",
    "[Conditional] Model 5-year overall survival in breast cancer patients from stage and receptor status, compared across race.",
    "[Blocked] Which treatment should this patient get given she is ER positive and HER2 negative?",
    "[Blocked] Does BRCA1/2 status improve 2-year recurrence prediction?",
    "[Insufficient] Is the data good?",
]

for q in QUESTIONS:
    label, text = q.split("] ", 1)
    print("=" * 80, f"\nExpected {label}]  {text}\n")
    try:
        spec = parse_question(text, dictionary, columns)
    except Exception as e:
        print(f"Parser call failed: {type(e).__name__}: {e}")
        continue
    print(json.dumps(spec, indent=2))
    try:
        spec_from_dict(spec)
        print("Spec validation: passed")
    except SpecError as e:
        print(f"Spec validation: FAILED -> engine returns Insufficient evidence ({e})")
    out = evaluate_dataset(data, dictionary, spec=spec)
    print(f"Verdict: {out['verdict']}  rules: {[f['rule_id'] for f in out['findings']]}\n")
