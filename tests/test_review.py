"""The review step: decisions must fit the signed verdict, approvals need acknowledged evidence,
and edited results or reviews are rejected. Run: python tests/test_review.py"""
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from cohort_firewall import review as rv  # noqa: E402
from cohort_firewall.engine import evaluate_dataset  # noqa: E402
from cohort_firewall.review import ReviewError, review_question, review_release, verify_review  # noqa: E402

V = ROOT / "data" / "variants"


def result(case):
    f = V / case
    d = f / "dictionary.json"
    return evaluate_dataset((f / "data.csv").read_bytes(), json.loads(d.read_text()) if d.exists() else None,
                            spec=json.loads((f / "spec.json").read_text()))


def expect_error(fn, *a, **k):
    try:
        fn(*a, **k)
    except ReviewError:
        return True
    return False


def run():
    rv.REVIEWS = Path(tempfile.mkdtemp())
    checks = []
    ready, cond, blocked = result("clean"), result("feature_missingness"), result("phi")
    rid = lambda r: [f["rule_id"] for f in r["findings"]]

    rec = review_question(ready, "A. Reviewer", "data steward", "approve", [], "")
    checks.append(("Ready can be approved, record verifies", verify_review(rec)))
    bad = copy.deepcopy(rec); bad["review"]["decision"] = "reject"
    checks.append(("edited review fails verification", not verify_review(bad)))
    checks.append(("Conditional cannot use plain approve",
                   expect_error(review_question, cond, "A", "r", "approve", rid(cond), "fine by me ok")))
    checks.append(("Conditional approval needs every finding acknowledged",
                   expect_error(review_question, cond, "A", "r", "approve_with_conditions", [], "impute HER2 first")))
    checks.append(("Conditional approval needs a note",
                   expect_error(review_question, cond, "A", "r", "approve_with_conditions", rid(cond), "")))
    ok = review_question(cond, "A", "r", "approve_with_conditions", rid(cond), "Impute HER2 and report it.")
    checks.append(("Conditional approved with acknowledgement and note", ok["review"]["decision"] == "approve_with_conditions"))
    checks.append(("Blocked can never be approved",
                   expect_error(review_question, blocked, "A", "r", "approve", rid(blocked), "approve anyway please")))
    checks.append(("Blocked can be rejected with a note",
                   bool(review_question(blocked, "A", "r", "reject", [], "Remove identifiers first."))))
    forged = copy.deepcopy(blocked); forged["certificate"]["payload"]["verdict"] = "READY"
    checks.append(("result with an edited verdict is refused",
                   expect_error(review_question, forged, "A", "r", "approve", [], "")))
    checks.append(("reviewer name required", expect_error(review_question, ready, " ", "r", "approve", [], "")))

    # Control Tower release review
    from fake_tcga import make_baseline, make_challenge_repo, make_release
    from cohort_firewall.tower.run import run_tower
    t = Path(tempfile.mkdtemp())
    make_baseline(t / "b")
    make_challenge_repo(t / "c", t / "b")
    rel = t / "c" / "data" / "tcga-brca" / "releases" / "r1"
    make_release(t / "b", rel, [{"type": "swap", "file": "protein_rppa.tsv.gz"}], seed=9)
    doc = run_tower(t / "c", rel)
    verd = {a["id"]: a["verdict"] for a in doc["analyses"]}
    checks.append(("release review: Blocked A1 cannot be approved",
                   expect_error(review_release, doc, "A", "r", {"A1": "approve", "A2": "approve"},
                                [f["id"] for f in doc["findings"]], "looks fine to me")))
    rec2 = review_release(doc, "A", "r", {"A1": "reject", "A2": "approve"}, [], "Restore the swapped samples.")
    checks.append(("release review recorded and verifies", verify_review(rec2) and verd == {"A1": "Blocked", "A2": "Ready"}))
    forged2 = copy.deepcopy(doc)
    for a in forged2["analyses"]:
        a["verdict"] = "Ready"
    checks.append(("edited analysis verdicts are refused",
                   expect_error(review_release, forged2, "A", "r", {"A1": "approve", "A2": "approve"}, [], "")))

    for name, okay in checks:
        print(f"{'PASS' if okay else 'FAIL'}  {name}")
    return all(o for _, o in checks)


def test_review():
    assert run()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
