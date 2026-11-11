"""Command line: compare a baseline release with a new one and write findings.json.

  python -m cohort_firewall.tower --challenge-repo ~/oncosys-hackathon-challenge \\
      --b ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B --out findings.json

--a defaults to the challenge repo's frozen release (data/tcga-brca/raw).
"""
import argparse
import json
import sys
from pathlib import Path

from .analyses import evaluate_analyses, load_reference_analyses
from .diff import diff_releases
from .findings import build_findings
from .releases import frozen_checksums, load_release


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--challenge-repo", type=Path, default=Path("~/oncosys-hackathon-challenge").expanduser())
    ap.add_argument("--a", type=Path, help="baseline release folder (default: <repo>/data/tcga-brca/raw)")
    ap.add_argument("--b", type=Path, required=True, help="new release folder")
    ap.add_argument("--out", type=Path, default=Path("findings.json"))
    ap.add_argument("--team", default="Cohort Firewall")
    ap.add_argument("--no-rna", action="store_true", help="skip the 64 MB RNA file")
    args = ap.parse_args(argv)
    repo = args.challenge_repo.expanduser()
    path_a = (args.a or repo / "data" / "tcga-brca" / "raw").expanduser()
    path_b = args.b.expanduser()
    for p in (repo, path_a, path_b):
        if not p.exists():
            sys.exit(f"Not found: {p}")

    rel_a = load_release(path_a, "frozen-A" if args.a is None else path_a.name, include_rna=not args.no_rna)
    rel_b = load_release(path_b, path_b.name, include_rna=not args.no_rna)
    frozen = frozen_checksums(repo)
    unverified = sorted(f for f, h in rel_a.file_hashes.items() if frozen.get(f) != h["file"])
    print(f"Baseline {rel_a.name}: {len(rel_a.files)} files, "
          f"{'all match frozen checksums' if not unverified else 'UNVERIFIED: ' + ', '.join(unverified)}")
    print(f"New release {rel_b.name}: {len(rel_b.files)} files")

    changes = diff_releases(rel_a, rel_b)
    analyses = load_reference_analyses(repo)
    runs = evaluate_analyses(analyses, path_a, path_b, changes)
    question = (f"Is release {rel_b.name} still fit for the protected analyses "
                f"({', '.join(a.id for a in analyses)}) that were run on {rel_a.name}?")
    doc = build_findings(rel_a, rel_b, changes, runs, unverified, args.team, question)
    args.out.write_text(json.dumps(doc, indent=2))

    print(f"\n{len(doc['findings'])} findings, {len(doc['repairs'])} proposed repairs")
    for f in doc["findings"]:
        print(f"  {f['id']:4s} [{f['severity']:6s}] {f['summary']}  -> affects {', '.join(f['affects_analyses']) or 'none'}")
    print("\nAnalyses:")
    for a in doc["analyses"]:
        print(f"  {a['id']}: {a['verdict']:22s} ({a['status']}) {a['reason']}")
        for r in a["verdict_rules"]:
            print(f"      [{r['rule_id']}] {r['reason']}")
    print(f"\nOverall: {doc['verdict']}   ->  {args.out}")


if __name__ == "__main__":
    main()
