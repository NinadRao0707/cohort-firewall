"""Regression + evaluation suite. Works with pytest, or run directly: python tests/test_variants.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cohort_firewall.certificate import verify  # noqa: E402
from cohort_firewall.engine import evaluate_dataset  # noqa: E402

VARIANTS = ROOT / "data" / "variants"


def _run(case):
    folder = VARIANTS / case
    dct = folder / "dictionary.json"
    return evaluate_dataset(
        (folder / "data.csv").read_bytes(),
        json.loads(dct.read_text()) if dct.exists() else None,
        spec=json.loads((folder / "spec.json").read_text()),
    )


def _cases():
    return json.loads((VARIANTS / "manifest.json").read_text())


def test_all_variants():
    failures = []
    for c in _cases():
        out = _run(c["case"])
        fired = {f["rule_id"] for f in out["findings"]}
        if out["verdict"] != c["expected_verdict"] or not set(c["expected_rules"]) <= fired:
            failures.append((c["case"], c["expected_verdict"], out["verdict"], c["expected_rules"], sorted(fired)))
        assert verify(out["certificate"]), f"certificate failed to verify for {c['case']}"
    assert not failures, failures


def test_tampered_certificate_fails():
    out = _run("phi")
    cert = out["certificate"]
    cert["payload"]["verdict"] = "READY"
    assert not verify(cert)


def test_injection_cannot_reach_report():
    out = _run("prompt_injection")
    assert "ignore all previous" not in json.dumps(out).lower()


if __name__ == "__main__":
    rows, ok = [], True
    for c in _cases():
        out = _run(c["case"])
        fired = sorted({f["rule_id"] for f in out["findings"]})
        passed = out["verdict"] == c["expected_verdict"] and set(c["expected_rules"]) <= set(fired)
        ok &= passed
        rows.append((c["case"], c["expected_verdict"], out["verdict"], ", ".join(fired) or "-",
                     "PASS" if passed else "FAIL"))
    w = [max(len(r[i]) for r in rows + [("case", "expected", "actual", "rules fired", "")]) for i in range(5)]
    hdr = ("case", "expected", "actual", "rules fired", "")
    print("  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
    for r in rows:
        print("  ".join(x.ljust(w[i]) for i, x in enumerate(r)))
    for t in (test_tampered_certificate_fails, test_injection_cannot_reach_report):
        try:
            t(); print(f"{t.__name__}: PASS")
        except AssertionError as e:
            ok = False; print(f"{t.__name__}: FAIL {e}")
    sys.exit(0 if ok else 1)
