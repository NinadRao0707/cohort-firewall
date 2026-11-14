"""Live demo: try to quietly change a past verdict, and watch the audit ledger catch it.

Works on a COPY of your ledger; the real one is never touched.
  python scripts/tamper_demo.py
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cohort_firewall import ledger  # noqa: E402

real = ledger.path()
if not real.exists() or not ledger.read_all():
    sys.exit("The ledger is empty. Run a release check first.")
copy = Path(tempfile.mkdtemp()) / "ledger-copy.jsonl"
shutil.copy(real, copy)
os.environ["CF_LEDGER_PATH"] = str(copy)
lines = copy.read_text().splitlines()
target = max(i for i, l in enumerate(lines) if json.loads(l)["event"] in ("release_check", "question_check", "review"))
e = json.loads(lines[target])
before = e["subject"].get("verdict") or e["subject"].get("decision")
e["subject"]["verdict"] = "Ready"
lines[target] = json.dumps(e, sort_keys=True)
copy.write_text("\n".join(lines) + "\n")
print(f"Changed entry #{e['seq']} ({e['event']}) from {before!r} to 'Ready' in a copy of the ledger.\n")
r = ledger.verify(copy)
print("Ledger intact." if r["ok"] else "LEDGER BROKEN:")
for p in r["problems"]:
    print("  -", p)
print(f"\nThe real ledger is untouched: {ledger.verify(real)['entries']} entries, "
      f"intact = {ledger.verify(real)['ok']}.")
