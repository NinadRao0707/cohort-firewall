"""One function the CLI, the API and the sample exporter all call."""
from __future__ import annotations

from pathlib import Path

from .analyses import evaluate_analyses, load_reference_analyses
from .diff import diff_releases
from .findings import build_findings
from .releases import frozen_checksums, load_release


def run_tower(challenge_repo: Path, path_b: Path, path_a: Path | None = None,
              team: str = "Cohort Firewall", include_rna: bool = True,
              include_summaries: bool = True) -> dict:
    repo = Path(challenge_repo).expanduser()
    a = Path(path_a).expanduser() if path_a else repo / "data" / "tcga-brca" / "raw"
    b = Path(path_b).expanduser()
    for p in (repo, a, b):
        if not p.exists():
            raise FileNotFoundError(str(p))
    import time
    from .releases import LAYOUT
    t0 = time.time()
    cache = Path(__file__).resolve().parents[2] / "outputs" / "cache"
    # Compare the files the new release actually has. Envelope releases omit RNA by design, so a
    # baseline file the new release doesn't carry is listed as "not compared", never as a finding.
    in_b = {f for f in LAYOUT if (b / f).exists() and (include_rna or not f.startswith("rna_"))}
    not_compared = sorted(f for f in LAYOUT if (a / f).exists() and f not in in_b)
    rel_a = load_release(a, "frozen-A" if path_a is None else a.name, include_rna=include_rna,
                         cache_dir=cache, only=in_b)
    t1 = time.time()
    rel_b = load_release(b, release_name(b), include_rna=include_rna)
    frozen = frozen_checksums(repo)
    unverified = sorted(f for f, h in rel_a.file_hashes.items() if frozen.get(f) != h["file"])
    changes = diff_releases(rel_a, rel_b)
    analyses = load_reference_analyses(repo)
    runs = evaluate_analyses(analyses, a, b, changes)
    question = (f"Is release {rel_b.name} still fit for the protected analyses "
                f"({', '.join(x.id for x in analyses)}) that were run on {rel_a.name}?")
    doc = build_findings(rel_a, rel_b, changes, runs, unverified, team, question,
                         include_summaries=include_summaries)
    # How much each rerun analysis moved relative to sampling noise, and whether the repairs fix it.
    from .impact import clear_cache, noise, repair_simulation, sentence
    clear_cache()
    impact_lines, impact_short = [], []
    import os as _os
    for r in runs:
        if r.after is None or _os.environ.get("CF_IMPACT", "1") == "0":
            continue
        try:
            m = noise(r, a)
            rp = repair_simulation(r, a, b, doc["findings"])
        except Exception as e:  # never let the extra analysis break the comparison
            m, rp = None, None
            doc.setdefault("x_impact_errors", []).append(f"{r.analysis.id}: {e}")
        entry = next(x for x in doc["analyses"] if x["id"] == r.analysis.id)
        text = sentence(r.analysis.id, m, rp, entry.get("verdict", ""))
        if m:
            short = f"{r.analysis.id} moved {m['ratio']:g}× its sampling noise ({m['label']})"
            if rp:
                short += "; the proposed repairs bring it back to baseline" if rp["back_to_baseline"] else \
                    f"; after the proposed repairs it is {rp['after_all_repairs']:g} (baseline {rp['baseline']:g})"
            impact_short.append((short, m["label"] != "beyond sampling noise" and entry.get("verdict") != "Ready"))
        import json as _json
        entry["x_impact"] = _json.loads(_json.dumps({"noise": m, "repair": rp, "sentence": text},
                                                    default=lambda o: o.item() if hasattr(o, "item") else str(o)))
        if text:
            impact_lines.append(text)
    if impact_short:
        line = ". ".join(s for s, _ in impact_short) + "."
        if any(small for _, small in impact_short):
            line += " Small shifts don't make a release safe: verdicts come from what changed, not how much."
        doc["plain_summary"] = doc["plain_summary"].replace(" A person must review", " " + line + " A person must review", 1)

    from ..disclosure import NOTE, suppress
    doc["x_shareable_summary"] = {"text": suppress(doc["plain_summary"]), "note": NOTE}

    doc["baseline_unverified_files"] = unverified
    doc["not_compared"] = not_compared
    if not_compared:
        doc["limitations"].append(f"Not in this release, so not compared: {', '.join(not_compared)}. "
                                  "An analysis that needs one of these files cannot be rerun and says so.")
    doc["timing_seconds"] = {"baseline": round(t1 - t0, 1), "total": round(time.time() - t0, 1)}
    return doc


def release_name(path: Path) -> str:
    """envelopes/opened/E07/release -> "E07"; data/tcga-brca/releases/practice-B -> "practice-B"."""
    path = Path(path)
    return path.parent.name if path.name == "release" else path.name


def _is_release(p: Path) -> bool:
    return p.is_dir() and any((p / f).exists() for f in ("clinical.tsv", "protein_rppa.tsv.gz"))


def release_folders(challenge_repo: Path) -> dict[str, Path]:
    """Every release a reviewer can compare: built releases and opened envelopes, by display name."""
    repo = Path(challenge_repo).expanduser()
    found: dict[str, Path] = {}
    opened = repo / "envelopes" / "opened"
    if opened.exists():
        for e in sorted(opened.iterdir()):
            if _is_release(e / "release"):
                found[f"envelope {e.name}"] = e / "release"
    built = repo / "data" / "tcga-brca" / "releases"
    if built.exists():
        for p in sorted(built.iterdir()):
            if _is_release(p):
                found[p.name] = p
    return found


def list_releases(challenge_repo: Path) -> list[dict]:
    return [{"name": n, "files": sorted(x.name for x in p.iterdir() if x.is_file() and x.name != "CHANGES.json")}
            for n, p in release_folders(challenge_repo).items()]
