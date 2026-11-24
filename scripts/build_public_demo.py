"""Build the synthetic Release-check example for the hosted (public) web demo.

Every value is random and every ID starts with DEMO-, so nothing in the hosted demo can be mistaken
for, or collide with, a real TCGA sample. Real TCGA runs stay local. Output:
  web/public/samples/tower_demo.json

  python scripts/build_public_demo.py
"""
import gzip
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from fake_tcga import make_baseline, make_challenge_repo, make_release  # noqa: E402
from cohort_firewall.tower.run import run_tower  # noqa: E402


def demo_ids(folder: Path):
    """Rewrite every TCGA- prefix to DEMO- (same length, so barcode positions still work)."""
    for f in folder.iterdir():
        if f.suffix == ".gz":
            text = gzip.open(f, "rt").read().replace("TCGA-", "DEMO-")
            with gzip.open(f, "wt") as out:
                out.write(text)
        elif f.suffix in (".tsv", ".csv"):
            f.write_text(f.read_text().replace("TCGA-", "DEMO-"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "frozen-demo"
        make_baseline(base, seed=2026)
        demo_ids(base)
        repo = tmp / "challenge"
        make_challenge_repo(repo, base)
        rel = repo / "data" / "tcga-brca" / "releases" / "demo-release"
        make_release(base, rel, [
            {"type": "swap", "file": "protein_rppa.tsv.gz"},
            {"type": "new_duplicate", "file": "protein_rppa.tsv.gz"},
            {"type": "drop", "file": "protein_rppa.tsv.gz", "count": 3},
            {"type": "relabel", "file": "clinical.tsv", "column": "PAM50Call_RNAseq", "value": "Basal", "count": 4},
        ], seed=14)
        demo_ids(rel)
        doc = run_tower(repo, rel, team="Insufficient Evidence (synthetic demo)")
    doc["x_demo"] = {"synthetic": True,
                     "note": "Synthetic demo: random values, made-up DEMO- IDs. Not TCGA data."}
    text = json.dumps(doc, indent=2)
    assert "TCGA-" not in text.replace("TCGA-BRCA", ""), "a TCGA-style ID leaked into the demo"
    out = ROOT / "web" / "public" / "samples" / "tower_demo.json"
    out.write_text(text)
    print(f"wrote {out.relative_to(ROOT)}: {doc['verdict']}, {len(doc['findings'])} findings, "
          f"{len(doc.get('x_summaries', []))} summaries, analyses "
          f"{ {a['id']: a['verdict'] for a in doc['analyses']} }")


if __name__ == "__main__":
    main()
