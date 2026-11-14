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
    """Cite only samples that changed. For a copy, the sample whose profile was copied is unchanged:
    it is named in the note, not cited as a changed sample."""
    if change.type in {"copied_profile", "new_duplicate"} and len(change.samples) > 1:
        src = change.samples[1]
        return [{"kind": "sample", "id": change.samples[0], "release": rel_b, "file": change.file,
                 "note": f"carries the exact profile of {src}, which is unchanged"}]
    refs = [{"kind": "sample", "id": s, "release": rel_b, "file": change.file} for s in change.samples[:limit]]
    if len(change.samples) > limit:
        refs.append({"kind": "file", "id": change.file, "release": rel_b,
                     "note": f"{len(change.samples) - limit} more samples not listed"})
    return refs or [{"kind": "file", "id": change.file, "release": rel_b}]


DERIVED = {"coverage_loss", "count_masks_membership"}
INTEGRITY = {"swap": "measurements are attached to the wrong samples",
             "copied_profile": "a sample carries another sample's measurements",
             "new_duplicate": "the same measurement is counted under two sample IDs"}


def _moved(runs: list[AnalysisRun], ids: list[str]) -> str:
    """The headline value each affected analysis moved by, e.g. 'A1 difference 3.051 → 3.019'."""
    out = []
    for r in runs:
        if r.analysis.id not in ids or not r.before or not r.after:
            continue
        nums = {k: (r.before[k], r.after[k]) for k in r.before
                if isinstance(r.before.get(k), (int, float)) and isinstance(r.after.get(k), (int, float))
                and r.before[k] != r.after[k] and not k.startswith("n_")}
        if not nums:
            continue
        k = "difference" if "difference" in nums else max(nums, key=lambda x: abs(nums[x][1] - nums[x][0]) / (abs(nums[x][0]) or 1))
        out.append(f"{r.analysis.id} {k.replace('_', ' ')} {nums[k][0]:g} → {nums[k][1]:g}")
    return f" ({'; '.join(out)})" if out else ""


def _rate(ch: Change, affects: list[str], runs: list[AnalysisRun]) -> tuple[str, str]:
    """Severity by how much the change could move a protected analysis's answer, with the reason."""
    who = ", ".join(affects)
    moved = _moved(runs, affects)
    if ch.type in INTEGRITY:
        if affects:
            return "high", f"High: {INTEGRITY[ch.type]} in data {who} uses, so its result can't be trusted{moved}."
        return "medium", (f"Medium: no protected analysis uses these samples, but any analysis of {ch.file} "
                          f"would be wrong because {INTEGRITY[ch.type]}.")
    if ch.type == "label_change":
        cols = ", ".join(ch.detail.get("key_labels") or ch.detail.get("columns", [])[:3])
        if ch.detail.get("key_labels") and affects:
            return "high", f"High: {who} groups or filters by {cols}, which changed for this sample{moved}."
        if ch.detail.get("key_labels"):
            return "medium", f"Medium: {cols} is a key clinical label, but this sample isn't in a protected analysis."
        return "low", f"Low: the changed fields ({cols}) aren't used to group or filter the protected analyses."
    if ch.type == "coverage_loss":
        d = ch.detail
        drop = (d["before"] - d["after"]) / max(d["before"], 1)
        level = "medium" if affects and drop >= 0.05 else "low"
        where = f"the lost profiles are in data {who} uses" if affects else "no protected analysis uses these samples"
        return level, (f"{level.title()}: {d['subgroup_column']} = {d['subgroup']} lost {d['before'] - d['after']} of "
                       f"{d['before']} genuine profiles ({drop:.1%}); {where}. Restates the changes above.")
    if ch.type == "count_masks_membership":
        return "medium", ("Medium: restates the removals and copies above; reported because the unchanged "
                          "sample count would hide them from a count check.")
    if affects:
        what = {"removed": "removes samples from", "added": "adds samples to", "values_missing": "loses values in",
                "values_edited": "edits values in"}.get(ch.type, "changes")
        return "medium", f"Medium: {what} the data {who} uses, changing who or what is counted{moved}."
    return "low", f"Low: no protected analysis reads the samples or fields that changed in {ch.file}."


def build_findings(rel_a: Release, rel_b: Release, changes: list[Change], runs: list[AnalysisRun],
                   baseline_unverified: list[str], team: str, question: str,
                   include_summaries: bool = True) -> dict:
    """include_summaries=False leaves out findings that only summarize other findings
    (coverage per subgroup, count-masked membership), for checkers that score each finding."""
    if not include_summaries:
        changes = [c for c in changes if c.type not in DERIVED]
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
        elif ch.type == "count_masks_membership":
            d = ch.detail
            summary = (f"{ch.file}: sample count unchanged ({d['n']}) but membership changed: "
                       f"{d['removed']} sample(s) removed and {d['added']} added. A count check alone would miss this.")
        elif ch.type == "coverage_loss":
            d = ch.detail
            summary = (f"{ch.file}: genuine profiles for {d['subgroup_column']} = {d['subgroup']!r} "
                       f"fell from {d['before']} to {d['after']}")
        else:
            a = ch.samples[0] if ch.samples else ""
            b = ch.samples[1] if len(ch.samples) > 1 else ""
            summary = SUMMARY.get(ch.type, ch.type).format(a=a, b=b, file=ch.file, n=len(ch.samples))
        severity, severity_reason = _rate(ch, affects, runs)
        findings.append({
            "id": fid, "kind": ch.kind, "summary": summary, "severity": severity, "confidence": "high",
            "x_severity_reason": severity_reason,
            "evidence": _evidence(ch, rel_b.name),
            "affects_analyses": affects, "not_affected_analyses": not_affected,
            "limitation": LIMITATION.get(ch.type, "Detected by comparing exact values between releases."),
            "needs_human_review": severity in {"high", "medium"} or bool(affects),
            **({"x_summary_of_other_findings": True} if ch.type in DERIVED else {}),
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
                 "affected_by": sorted({ids_by_change[id(c)] for c in r.changes if id(c) in ids_by_change},
                                       key=lambda x: int(x[1:])),
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
    doc.update(_tower_summary(rel_a.name, rel_b.name, findings, analyses, repairs))
    hashes = json.dumps(doc["data"], sort_keys=True).encode()
    from ..review import tower_binding
    doc["certificate"] = issue(dataset_bytes=hashes, dictionary=None,
                               spec_json=tower_binding(question, analyses),
                               policy_version=Policy.load(TOWER_POLICY).version,
                               policy_sha256=Policy.load(TOWER_POLICY).sha256, verdict=overall,
                               rule_ids=[f["rule_id"] for e in vds.values() for f in e["findings"]])
    return doc


ACTION_TEXT = {
    "restore_from_previous_release": "Restore {n} sample profile(s) in {file} from the baseline release",
    "exclude": "Exclude {n} new sample ID(s) in {file} that copy another sample's profile",
    "flag_for_review": "Check {n} changed sample(s) in {file} against the source",
}
ACTION_ORDER = {"restore_from_previous_release": 0, "exclude": 1, "flag_for_review": 2}
KIND_TEXT = {"sample_swap": "sample swap(s)", "duplicate": "profile(s) copied onto other IDs",
             "membership_change": "membership change(s)", "label_conflict": "clinical label change(s)",
             "missing_data": "missing-data change(s)", "other": "other change(s)"}


def _tower_summary(name_a: str, name_b: str, findings: list[dict], analyses: list[dict], repairs: list[dict]) -> dict:
    """Plain-English summary and ranked next steps for a release comparison."""
    core = [f for f in findings if not f.get("x_summary_of_other_findings")]
    counts: dict[str, int] = {}
    for f in core:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    changed = ", ".join(f"{n} {KIND_TEXT.get(k, k)}" for k, n in counts.items()) or "nothing"
    parts = []
    for a in analyses:
        if a["status"] == "not_rerun":
            parts.append(f"{a['id']} is unaffected and was not rerun")
        else:
            parts.append(f"{a['id']} is {a['verdict']}"
                         + (f" because of {', '.join(a['affected_by'][:4])}" if a.get("affected_by") else ""))
    masked = next((f["summary"] for f in findings if "count unchanged" in f["summary"]), "")
    cov = [f for f in findings if f.get("x_summary_of_other_findings") and "genuine profiles for" in f["summary"]]
    concentrated = ""
    drops = []
    for f in cov:
        import re as _re
        m = _re.search(r"for (\S+) = '([^']+)' fell from (\d+) to (\d+)", f["summary"])
        if m:
            b, a2 = int(m.group(3)), int(m.group(4))
            drops.append((m.group(2), m.group(1), b - a2, b, (b - a2) / max(b, 1)))
    if len(drops) >= 2:
        drops.sort(key=lambda x: -x[4])
        top, rest = drops[0], drops[1:]
        same_col = [d for d in rest if d[1] == top[1]]
        if top[4] >= 0.05 and all(d[4] * 3 <= top[4] for d in same_col):
            others = max((d[4] for d in same_col), default=0)
            versus = (f"against {others:.1%} or less for every other {top[1]} group" if others
                      else f"while no other {top[1]} group lost any")
            concentrated = (f"The losses are concentrated in one group: {top[0]} lost {top[2]} of {top[3]} genuine "
                            f"profiles ({top[4]:.1%}), {versus}, so results for {top[0]} move more than the "
                            f"total count suggests. ")
    summary = (f"Compared with {name_a}, release {name_b} has {changed}. " + concentrated
               + ((lambda t: t[:1].upper() + t[1:])(masked.split(":", 1)[1].strip().rstrip(".")) + ". " if masked else "")
               + "; ".join(parts) + ". A person must review before the new release is used.")
    affected_by_finding = {}
    for a in analyses:
        for fid in a.get("affected_by", []):
            affected_by_finding.setdefault(fid, set()).add(a["id"])
    groups: dict[tuple, dict] = {}
    for r in repairs:
        file = r["targets"][0].get("file", "") if r["targets"] else ""
        g = groups.setdefault((r["action"], file), {"action": r["action"], "file": file, "samples": [], "findings": []})
        g["samples"] += [t["id"] for t in r["targets"]]
        g["findings"] += r["addresses"]
    steps = []
    for (action, file), g in sorted(groups.items(), key=lambda kv: ACTION_ORDER.get(kv[0][0], 9)):
        unblocks = sorted({a for fid in g["findings"] for a in affected_by_finding.get(fid, set())})
        steps.append({"rank": len(steps) + 1,
                      "action": ACTION_TEXT.get(action, action).format(n=len(set(g["samples"])), file=file),
                      "samples": sorted(set(g["samples"]))[:12], "n_samples": len(set(g["samples"])),
                      "resolves": sorted(set(g["findings"])), "affects_analyses": unblocks})
    return {"plain_summary": summary, "next_steps": steps}
