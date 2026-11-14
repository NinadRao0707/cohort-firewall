"""The audit ledger detects edited, deleted, inserted and reordered entries. Run: python tests/test_ledger.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run():
    tmp = Path(tempfile.mkdtemp()) / "ledger.jsonl"
    os.environ["CF_LEDGER_PATH"] = str(tmp)
    from cohort_firewall import ledger
    for i in range(5):
        ledger.append("release_check", {"cert_id": f"c{i}", "verdict": "Blocked"})
    good = tmp.read_text()
    lines = good.splitlines()
    checks = [("intact chain verifies", ledger.verify()["ok"] and ledger.verify()["entries"] == 5)]

    def broken(text):
        tmp.write_text(text)
        r = ledger.verify()
        tmp.write_text(good)
        return not r["ok"], r["problems"][:1]

    e = json.loads(lines[2]); e["subject"]["verdict"] = "Ready"
    ok, why = broken("\n".join(lines[:2] + [json.dumps(e)] + lines[3:]) + "\n")
    checks.append(("edited verdict detected (entry 3)", ok and "entry 3" in why[0]))
    ok, why = broken("\n".join(lines[:1] + lines[2:]) + "\n")
    checks.append(("deleted entry detected", ok))
    ok, why = broken("\n".join([lines[1], lines[0]] + lines[2:]) + "\n")
    checks.append(("reordered entries detected", ok))
    e = json.loads(lines[2]); e["subject"]["verdict"] = "Ready"
    from cohort_firewall.ledger import _hash
    e["hash"] = _hash(e)          # attacker recomputes the hash but can't re-sign
    ok, why = broken("\n".join(lines[:2] + [json.dumps(e)] + lines[3:]) + "\n")
    checks.append(("rehashed forgery detected (signature or chain)", ok))
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    return all(p for _, p in checks)


def test_ledger():
    assert run()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
