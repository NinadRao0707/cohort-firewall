"""One function the CLI, the API and the sample exporter all call."""
from __future__ import annotations

from pathlib import Path

from .analyses import evaluate_analyses, load_reference_analyses
from .diff import diff_releases
from .findings import build_findings
from .releases import frozen_checksums, load_release


def run_tower(challenge_repo: Path, path_b: Path, path_a: Path | None = None,
              team: str = "Cohort Firewall", include_rna: bool = True) -> dict:
    repo = Path(challenge_repo).expanduser()
    a = Path(path_a).expanduser() if path_a else repo / "data" / "tcga-brca" / "raw"
    b = Path(path_b).expanduser()
    for p in (repo, a, b):
        if not p.exists():
            raise FileNotFoundError(str(p))
    rel_a = load_release(a, "frozen-A" if path_a is None else a.name, include_rna=include_rna)
    rel_b = load_release(b, b.name, include_rna=include_rna)
    frozen = frozen_checksums(repo)
    unverified = sorted(f for f, h in rel_a.file_hashes.items() if frozen.get(f) != h["file"])
    changes = diff_releases(rel_a, rel_b)
    analyses = load_reference_analyses(repo)
    runs = evaluate_analyses(analyses, a, b, changes)
    question = (f"Is release {rel_b.name} still fit for the protected analyses "
                f"({', '.join(x.id for x in analyses)}) that were run on {rel_a.name}?")
    doc = build_findings(rel_a, rel_b, changes, runs, unverified, team, question)
    doc["baseline_unverified_files"] = unverified
    return doc


def list_releases(challenge_repo: Path) -> list[dict]:
    """Release folders a reviewer can compare against the frozen baseline."""
    root = Path(challenge_repo).expanduser() / "data" / "tcga-brca" / "releases"
    out = []
    if root.exists():
        for p in sorted(root.iterdir()):
            if p.is_dir() and any((p / f).exists() for f in ("clinical.tsv", "protein_rppa.tsv.gz")):
                out.append({"name": p.name, "files": sorted(x.name for x in p.iterdir()
                                                            if x.is_file() and x.name != "CHANGES.json")})
    return out
