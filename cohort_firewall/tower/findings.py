"""Turn detected changes and analysis reruns into per-analysis verdicts and findings.json (v0.2)."""
from __future__ import annotations

import json
from pathlib import Path

from .. import ENGINE_VERSION
from ..certificate import issue
from ..checks import CheckResult
from ..policy import Policy, evaluate
from .analyses import AnalysisRun
from .diff import Change
from .releases import Release

TOWER_POLICY = Path(__file__).resolve().parents[2] / "rules" / "tower_v0_1.yaml"
VERDICT_LABEL = {"READY": "Ready", "CONDITIONAL": "Conditional", "BLOCKED": "Blocked",
                 "INSUFFICIENT_EVIDENCE": "Insufficient Evidence"}
PRECEDENCE = ["BLOCKED", "INSUFFICIENT_EVIDENCE", "CONDITIONAL", "READY"]
SEVERITY = {"swap": "high", "copied_profile": "high", "new_duplicate": "high", "removed": "medium",
            "added": "low", "values_missing": "medium", "values_edited": "medium",
            "features_changed": "medium", "file_missing": "high", "file_added": "low"}
LIMITATION = {
    "swap": "Exact-match detection: a swap combined with small value edits appears as two value edits instead.",
    "copied_profile": "Exact-match detection: a near-copy with small edits appears as a value edit instead.",
    "new_duplicate": "Exact-match detection: a near-copy with small edits appears as a new sample instead.",
    "label_change": "The tool sees that a label changed, not which version is correct.",
    "coverage_loss": "Counts genuine profiles (not copies of another sample) per clinical subgroup, using the newer release's labels.",
    "count_masks_membership": "Compares sample IDs only; see the linked findings for what replaced the removed samples.",
}
GROUPABLE = {"added", "removed", "values_missing", "values_edited"}
SUMMARY = {
    "swap": "{a} and {b} exchanged profiles in {file}",
    "copied_profile": "{a} now carries the exact profile of {b} in {file}; its own profile is gone",
    "new_duplicate": "New sample {a} in {file} is an exact copy of {b}",
    "removed": "{n} sample(s) disappeared from {file}",
    "added": "{n} sample(s) appeared in {file}",
    "values_missing": "{n} sample(s) lost values in {file}",
    "values_edited": "{n} sample(s) have edited values in {file}",
    "features_changed": "Features (genes/proteins/columns) changed in {file}",
    "file_missing": "{file} is missing from the new release",
    "file_added": "{file} is new in this release",
}


def _metrics(run: AnalysisRun) -> dict:
    c = run.changes
    swaps = [x for x in c if x.type == "swap"]
    dups = [x for x in c if x.type in {"copied_profile", "new_duplicate"}]
    key_lbl = [x for x in c if x.type == "label_change" and x.detail.get("key_labels")]
    other_lbl = [x for x in c if x.type == "label_change" and not x.detail.get("key_labels")]
    mem = [x for x in c if x.type in {"added", "removed"}]
    vals = [x for x in c if x.type in {"values_missing", "values_edited"}]
    other = [x for x in c if x.type in {"features_changed", "file_missing", "file_added"}] + other_lbl
    return {
        "run_failed": bool(run.error), "error": run.error or "",
        "n_swaps": len(swaps), "swap_samples": sorted({s for x in swaps for s in x.samples})[:6],
        "n_duplicates": len(dups), "duplicate_samples": [x.samples[0] for x in dups][:6],
        "n_key_label_changes": len(key_lbl), "label_samples": [x.samples[0] for x in key_lbl][:6],
        "n_membership_changes": len(mem), "n_value_changes": len(vals), "n_other_changes": len(other),
        "n_integrity_issues": len(swaps) + len(dups) + len(key_lbl),
        "result_changed": run.status == "changed",
    }


def verdicts(runs: list[AnalysisRun], baseline_unverified: list[str]) -> dict[str, dict]:
    policy = Policy.load(TOWER_POLICY)
    out = {}
    for run in runs:
        results = [
            CheckResult("provenance", "ok", {"baseline_verified": not baseline_unverified,
                                             "unverified_files": baseline_unverified}),
            CheckResult("impact", "ok", _metrics(run)),
        ]
        ev = evaluate(results, policy, expected={"provenance", "impact"})
        out[run.analysis.id] = ev
    return out


def _evidence(change: Change, rel_b: str, limit: int = 25) -> list[dict]:
    refs = [{"kind": "sample", "id": s, "release": rel_b, "file": change.file} for s in change.samples[:limit]]
    if len(change.samples) > limit:
        refs.append({"kind": "file", "id": change.file, "release": rel_b,
                     "note": f"{len(change.samples) - limit} more samples not listed"})
    return refs or [{"kind": "file", "id": change.file, "release": rel_b}]


def build_findings(rel_a: Release, rel_b: Release, changes: list[Change], runs: list[AnalysisRun],
                   baseline_unverified: list[str], team: str, question: str) -> dict:
    ids_by_change: dict[int, str] = {}
    findings, repairs = [], []

    # group noisy change types per file
    grouped: dict[tuple, list[Change]] = {}
    singles: list[Change] = []
    for ch in changes:
        if ch.type in GROUPABLE:
            grouped.setdefault((ch.type, ch.file), []).append(ch)
        else:
            singles.append(ch)
    items = [(ch, [ch]) for ch in singles] + [
        (Change(t, f, [s for c in chs for s in c.samples], {"members": len(chs)}), chs)
        for (t, f), chs in grouped.items()]

    for n, (ch, members) in enumerate(items, 1):
        fid = f"F{n}"
        for m in members:
            ids_by_change[id(m)] = fid
        if ch.type in {"coverage_loss", "count_masks_membership"}:
            # summary findings: affect analyses that read this file and use the samples involved
            affects = sorted(r.analysis.id for r in runs if ch.file in r.analysis.inputs and r.before
                             and (set(ch.samples) & set(r.before.get("sample_ids", [])) or
                                  (ch.type == "count_masks_membership" and r.affected)))
        else:
            affects = sorted(r.analysis.id for r in runs if any(id(m) in {id(x) for x in r.changes} for m in members))
        not_affected = sorted(r.analysis.id for r in runs if r.analysis.id not in affects)
        if ch.type == "label_change":
            cols = ch.detail.get("columns", [])
            summary = (f"Clinical fields changed for {ch.samples[0]}: " +
                       ", ".join(f"{c} {ch.detail['before'].get(c)!r} → {ch.detail['after'].get(c)!r}"
                                 for c in cols[:4]))
            severity = "high" if ch.detail.get("key_labels") else "low"
        elif ch.type == "count_masks_membership":
            d = ch.detail
            summary = (f"{ch.file}: sample count unchanged ({d['n']}) but membership changed: "
                       f"{d['removed']} sample(s) removed and {d['added']} added. A count check alone would miss this.")
            severity = "high"
        elif ch.type == "coverage_loss":
            d = ch.detail
            summary = (f"{ch.file}: genuine profiles for {d['subgroup_column']} = {d['subgroup']!r} "
                       f"fell from {d['before']} to {d['after']}")
            drop = (d["before"] - d["after"]) / max(d["before"], 1)
            severity = "high" if drop >= 0.1 else "medium"
        else:
            a = ch.samples[0] if ch.samples else ""
            b = ch.samples[1] if len(ch.samples) > 1 else ""
            summary = SUMMARY.get(ch.type, ch.type).format(a=a, b=b, file=ch.file, n=len(ch.samples))
            severity = SEVERITY.get(ch.type, "medium")
        findings.append({
            "id": fid, "kind": ch.kind, "summary": summary, "severity": severity, "confidence": "high",
            "evidence": _evidence(ch, rel_b.name),
            "affects_analyses": affects, "not_affected_analyses": not_affected,
            "limitation": LIMITATION.get(ch.type, "Detected by comparing exact values between releases."),
            "needs_human_review": severity in {"high", "medium"} or bool(affects),
        })
        action, targets, why = None, [], ""
        if ch.type == "swap":
            action, why = "restore_from_previous_release", "Both samples' previous profiles are intact in the baseline release."
            targets = ch.samples
        elif ch.type == "copied_profile":
            action, why = "restore_from_previous_release", f"{ch.samples[0]}'s own profile exists in the baseline release."
            targets = ch.samples[:1]
        elif ch.type == "new_duplicate":
            action, why = "exclude", f"{ch.samples[0]} duplicates {ch.samples[1]} and has no profile of its own."
            targets = ch.samples[:1]
        elif ch.type in {"removed", "added", "label_change", "values_missing", "values_edited"}:
            action, why = "flag_for_review", "The tool cannot tell whether this change is a correction or an error."
            targets = ch.samples[:25]
        if action:
            repairs.append({"id": f"R{len(repairs) + 1}", "action": action,
                            "targets": [{"kind": "sample", "id": s, "release": rel_a.name if action.startswith("restore") else rel_b.name,
                                         "file": ch.file} for s in targets],
                            "justification": why, "addresses": [fid]})

    vds = verdicts(runs, baseline_unverified)
    analyses = []
    for r in runs:
        ev = vds[r.analysis.id]
        strip = lambda d: None if d is None else {k: v for k, v in d.items() if k != "sample_ids"} | \
            {"n_sample_ids": len(d.get("sample_ids", []))}
        entry = {"id": r.analysis.id, "status": r.status, "description": r.analysis.description,
                 "inputs": r.analysis.inputs, "reason": r.reason,
                 "verdict": VERDICT_LABEL[ev["verdict"]],
                 "verdict_rules": [{"rule_id": f["rule_id"], "verdict": VERDICT_LABEL[f["verdict"]],
                                    "reason": f["reason"], "remedy": f["remedy"]} for f in ev["findings"]],
                 "affected_by": sorted({ids_by_change[id(c)] for c in r.changes if id(c) in ids_by_change}),
                 "needs_human_review": ev["verdict"] != "READY"}
        if r.before is not None:
            entry["before"] = strip(r.before)
        if r.after is not None:
            entry["after"] = strip(r.after)
        analyses.append(entry)

    overall = next((v for v in PRECEDENCE if any(e["verdict"] == v for e in vds.values())), "READY")
    doc = {
        "format_version": "0.2",
        "producer": {"team": team, "product": "Cohort Control Tower", "track": "cohort-firewall"},
        "data": {"dataset": "TCGA-BRCA", "releases": [
            {"name": rel_a.name, "files": [{"file": f, "sha256": h["file"], "hash_of": "file"}
                                           for f, h in sorted(rel_a.file_hashes.items())]},
            {"name": rel_b.name, "files": [{"file": f, "sha256": h["content"], "hash_of": "content"}
                                           for f, h in sorted(rel_b.file_hashes.items())]},
        ]},
        "question": question,
        "verdict": VERDICT_LABEL[overall],
        "findings": findings,
        "analyses": analyses,
        "repairs": repairs,
        "limitations": [
            "Change detection compares exact values; edits that also alter a swapped or copied profile are reported as value edits.",
            "The tool shows what changed, not which release is correct. Every repair needs a person's decision.",
            "Research data-quality check only: no diagnosis, treatment recommendation, risk score or clinical claim.",
        ],
        "engine": {"name": "cohort-firewall", "version": ENGINE_VERSION,
                   "tower_policy": Policy.load(TOWER_POLICY).version},
    }
    hashes = json.dumps(doc["data"], sort_keys=True).encode()
    doc["certificate"] = issue(dataset_bytes=hashes, dictionary=None,
                               spec_json=json.dumps({"question": question, "analyses": [r.analysis.id for r in runs]}),
                               policy_version=Policy.load(TOWER_POLICY).version,
                               policy_sha256=Policy.load(TOWER_POLICY).sha256, verdict=overall,
                               rule_ids=[f["rule_id"] for e in vds.values() for f in e["findings"]])
    return doc
