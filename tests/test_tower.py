"""Control Tower scenario tests on FAKE releases (our own randomized changes).

Run: python tests/test_tower.py
If the real challenge repo is at ~/oncosys-hackathon-challenge (or CF_CHALLENGE_REPO), each
findings.json is also checked against its official schema.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from cohort_firewall.certificate import verify  # noqa: E402
from cohort_firewall.tower.__main__ import main  # noqa: E402
from fake_tcga import make_baseline, make_challenge_repo, make_release  # noqa: E402
from schema_check import check  # noqa: E402

REAL = Path(os.environ.get("CF_CHALLENGE_REPO", "~/oncosys-hackathon-challenge")).expanduser()
SCHEMA = REAL / "format" / "findings.schema.json"

# name, operations, expected verdicts per analysis, finding kinds that must appear
SCENARIOS = [
    ("no_change", [], {"A1": "Ready", "A2": "Ready"}, set()),
    ("protein_swap_opposite_er", [{"type": "swap", "file": "protein_rppa.tsv.gz"}],
     {"A1": "Blocked", "A2": "Ready"}, {"sample_swap"}),
    ("protein_copied_profiles", [{"type": "copy_over", "file": "protein_rppa.tsv.gz", "count": 3}],
     {"A1": "Blocked", "A2": "Ready"}, {"duplicate"}),
    ("pam50_relabel", [{"type": "relabel", "file": "clinical.tsv", "column": "PAM50Call_RNAseq",
                        "value": "Basal", "alt": "LumB", "count": 2}],
     {"A1": "Ready", "A2": "Blocked"}, {"label_conflict"}),
    ("er_relabel", [{"type": "relabel", "file": "clinical.tsv",
                     "column": "breast_carcinoma_estrogen_receptor_status", "value": "Negative",
                     "alt": "Positive", "count": 1}],
     {"A2": "Ready"}, {"label_conflict"}),   # A1 depends on whether that sample has protein data
    ("protein_drop", [{"type": "drop", "file": "protein_rppa.tsv.gz", "count": 3}],
     {"A1": "Conditional", "A2": "Ready"}, {"membership_change"}),
    ("protein_new_duplicate_id", [{"type": "new_duplicate", "file": "protein_rppa.tsv.gz"}],
     {"A1": "Blocked", "A2": "Ready"}, {"duplicate"}),
    ("count_unchanged_membership_changed", [{"type": "drop", "file": "protein_rppa.tsv.gz", "count": 1},
                                            {"type": "new_duplicate", "file": "protein_rppa.tsv.gz"}],
     {"A1": "Blocked", "A2": "Ready"}, {"membership_change", "duplicate"}),
    ("unused_file_edit", [{"type": "edit", "file": "mutation_gene_level.tsv.gz"}],
     {"A1": "Ready", "A2": "Ready"}, {"other"}),
    ("combined", [{"type": "swap", "file": "protein_rppa.tsv.gz"},
                  {"type": "copy_over", "file": "protein_rppa.tsv.gz", "count": 2},
                  {"type": "relabel", "file": "clinical.tsv", "column": "PAM50Call_RNAseq",
                   "value": "Her2", "alt": "LumA", "count": 1}],
     {"A1": "Blocked", "A2": "Blocked"}, {"sample_swap", "duplicate", "label_conflict"}),
]


def run_all(verbose=True):
    ok = True
    schema = json.loads(SCHEMA.read_text()) if SCHEMA.exists() else None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "baseline"
        make_baseline(base)
        repo = tmp / "challenge"
        make_challenge_repo(repo, base)
        for i, (name, ops, expected, kinds) in enumerate(SCENARIOS):
            rel = tmp / name
            applied = make_release(base, rel, ops, seed=100 + i)
            out = tmp / f"{name}.json"
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--challenge-repo", str(repo), "--b", str(rel), "--out", str(out)])
            doc = json.loads(out.read_text())
            got = {a["id"]: a["verdict"] for a in doc["analyses"]}
            found = {f["kind"] for f in doc["findings"]}
            problems = [f"{k}: expected {v}, got {got.get(k)}" for k, v in expected.items() if got.get(k) != v]
            problems += [f"missing finding kind {k}" for k in kinds - found]
            if name == "count_unchanged_membership_changed" and not any(
                    "count unchanged" in f["summary"] for f in doc["findings"]):
                problems.append("did not report that the count was unchanged while membership changed")
            if name == "protein_copied_profiles":
                # sources of copies keep their data: coverage loss must not exceed the overwritten samples
                lost = sum(1 for f in doc["findings"] if f["kind"] == "missing_data")
                srcs = {e["id"] for f in doc["findings"] if f["kind"] == "duplicate" for e in f["evidence"][1:2]}
                for f in doc["findings"]:
                    if f["kind"] == "missing_data" and srcs & {e["id"] for e in f["evidence"]}:
                        problems.append("coverage loss blamed on the source of a copy")
                if any(f["kind"] == "missing_data" and not f["affects_analyses"] for f in doc["findings"]):
                    problems.append("coverage finding affects no analysis")
            if not ops and doc["findings"]:
                problems.append("findings reported for an unchanged release")
            if any(a["status"] != "not_rerun" for a in doc["analyses"] if a["verdict"] == "Ready" and not a["affected_by"]):
                problems.append("an unaffected analysis was rerun")
            if not verify(doc["certificate"]):
                problems.append("certificate does not verify")
            if schema is not None:
                problems += check(doc, schema)
                fids = {f["id"] for f in doc["findings"]}
                problems += [f"repair {r['id']} addresses unknown finding" for r in doc["repairs"]
                             if not set(r["addresses"]) <= fids]
            ok &= not problems
            if verbose:
                print(f"{'PASS' if not problems else 'FAIL'}  {name:28s} {got}  findings={sorted(found)}")
                for p in problems:
                    print("      -", p)
                if problems:
                    print("      applied:", applied)
    if verbose and schema is None:
        print(f"(schema check skipped: {SCHEMA} not found)")
    return ok


def test_tower_scenarios():
    assert run_all(verbose=False)





def run_envelope_case(verbose=True):
    """Envelope releases have no RNA file. The baseline does. That must not be reported as a change,
    the release must be found under envelopes/opened/<name>/release/, and be named after the envelope."""
    import gzip
    import shutil
    from cohort_firewall.tower.run import release_folders, run_tower
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "baseline"
        make_baseline(base)
        repo = tmp / "challenge"
        make_challenge_repo(repo, base)
        with gzip.open(repo / "data" / "tcga-brca" / "raw" / "rna_hiseq.tsv.gz", "wt") as f:
            f.write("sample\tTCGA-AA-0001-01\nGENE1\t1.0\n")
        env = repo / "envelopes" / "opened" / "E07" / "release"
        make_release(base, env, [{"type": "swap", "file": "protein_rppa.tsv.gz"}], seed=77)
        problems = []
        folders = release_folders(repo)
        if "envelope E07" not in folders:
            problems.append(f"opened envelope not listed: {list(folders)}")
        doc = run_tower(repo, env)
        if any("rna_hiseq" in f["summary"] for f in doc["findings"]):
            problems.append("missing RNA reported as a finding")
        if doc.get("not_compared") != ["rna_hiseq.tsv.gz"]:
            problems.append(f"not_compared = {doc.get('not_compared')}")
        if doc["data"]["releases"][1]["name"] != "E07":
            problems.append(f"release named {doc['data']['releases'][1]['name']!r}, expected 'E07'")
        if {f["kind"] for f in doc["findings"]} != {"sample_swap", "missing_data"} or \
                {a["id"]: a["verdict"] for a in doc["analyses"]} != {"A1": "Blocked", "A2": "Ready"}:
            problems.append(f"unexpected result: {[f['kind'] for f in doc['findings']]}")
        if schema_path().exists():
            problems += check(doc, json.loads(schema_path().read_text()))
        if verbose:
            print(f"{'PASS' if not problems else 'FAIL'}  envelope_without_rna         "
                  f"{ {a['id']: a['verdict'] for a in doc['analyses']} }  not_compared={doc.get('not_compared')}")
            for p in problems:
                print("      -", p)
        return not problems


def schema_path():
    return SCHEMA


def test_envelope_without_rna():
    assert run_envelope_case(verbose=False)


if __name__ == "__main__":
    ok_all = run_all()
    ok_env = run_envelope_case()
    sys.exit(0 if ok_all and ok_env else 1)
