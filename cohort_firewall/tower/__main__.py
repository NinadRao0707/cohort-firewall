"""Command line: compare a baseline release with a new one and write findings.json.

  python -m cohort_firewall.tower --challenge-repo ~/oncosys-hackathon-challenge \\
      --b ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B --out findings.json

--a defaults to the challenge repo's frozen release (data/tcga-brca/raw).
"""
import argparse
import json
import sys
from pathlib import Path

from .run import run_tower


def main(argv=None):
    import sys as _sys
    for _stream in (_sys.stdout, _sys.stderr):   # Windows consoles: print arrows and ticks safely
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--challenge-repo", type=Path, default=Path("~/oncosys-hackathon-challenge").expanduser())
    ap.add_argument("--a", type=Path, help="baseline release folder (default: <repo>/data/tcga-brca/raw)")
    ap.add_argument("--b", type=Path, required=True, help="new release folder")
    ap.add_argument("--out", type=Path, default=Path("findings.json"))
    ap.add_argument("--team", default="Cohort Firewall")
    ap.add_argument("--no-rna", action="store_true", help="skip the 64 MB RNA file")
    ap.add_argument("--no-summary-findings", action="store_true",
                    help="leave out findings that only summarize others (coverage, count-masked membership)")
    args = ap.parse_args(argv)
    repo = args.challenge_repo.expanduser()
    path_a = (args.a or repo / "data" / "tcga-brca" / "raw").expanduser()
    path_b = args.b.expanduser()
    for p in (repo, path_a, path_b):
        if not p.exists():
            sys.exit(f"Not found: {p}")

    doc = run_tower(repo, path_b, args.a, team=args.team, include_rna=not args.no_rna,
                    include_summaries=not args.no_summary_findings)
    unverified = doc["baseline_unverified_files"]
    print(f"Baseline {doc['data']['releases'][0]['name']}: "
          f"{'all match frozen checksums' if not unverified else 'UNVERIFIED: ' + ', '.join(unverified)}")
    print(f"New release {doc['data']['releases'][1]['name']}: {len(doc['data']['releases'][1]['files'])} files")
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
