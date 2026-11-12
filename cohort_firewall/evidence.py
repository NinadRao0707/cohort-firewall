"""The evidence record behind each finding, in the event's findings-template shape.

For every finding: which check ran, which fields and rows it used, what was found, how that affects
THIS question, how material it is, how confident the check is, the evidence, the check's
limitation, the next step, and the evidence that would change the verdict.
"""
from __future__ import annotations

import csv
import io

CHECKS = {
    "metadata": ("Documentation, license and provenance", "high",
                 "Without source, license and patient-data details, the data's permitted use can't be confirmed.",
                 "Relies on what the data dictionary declares beyond the pinned checksums."),
    "scope": ("Permitted use", "high",
              "The event and this tool exclude diagnosis, treatment choices and patient risk scores.",
              "The wording guard is a phrase list; a cleverly worded clinical question could slip past it."),
    "spec_quality": ("Question clarity", "medium", "An unclear question can't be checked reliably.",
                     "Confidence comes from the question parser."),
    "columns": ("Required fields present", "high", "The question needs fields the data doesn't contain.",
                "Checks presence only, not meaning."),
    "cohort": ("Group being studied", "high", "No records match the group the question is about.",
               "Applies the card's conditions exactly as written."),
    "completeness": ("Missing values", "high",
                     "Missing values shrink the group that can be analysed and can bias it.",
                     "Counts missing values; it can't tell why they are missing."),
    "outcome_events": ("Enough outcome events", "high",
                       "Too few events make estimates unstable and models overfit.",
                       "10 events per model parameter is a rule of thumb, not a sample-size calculation."),
    "leakage": ("Unfair shortcuts (leakage)", "medium",
                "A field recorded after the outcome lets a model cheat; it won't work on new patients.",
                "Single-field check; strong legitimate predictors can also score high, and leakage spread "
                "across several fields can be missed."),
    "temporal": ("Follow-up length", "high",
                 "Patients not followed to the horizon have unknown outcomes; ignoring that biases results.",
                 "Uses the declared follow-up column and unit."),
    "units": ("Patients counted once", "high",
              "Counting samples as patients counts some people twice and overstates certainty.",
              "Uses the declared patient identifier."),
    "subgroups": ("Subgroup coverage (bias)", "high",
                  "With few patients in a group, the model's behaviour in that group can't be judged.",
                  "Minimum counts only; no comparison with a reference population."),
    "consistency": ("Records agree across sources", "high",
                    "Two sources disagree, so the label itself is uncertain for those records.",
                    "Compares the source pairs the dictionary declares; vocabularies are normalised."),
    "plausibility": ("Plausible values", "high",
                     "Impossible values point to data-entry errors that can distort results.",
                     "Uses the ranges the dictionary declares."),
    "phi": ("Direct identifiers", "medium",
            "Identifiers aren't permitted and create a re-identification risk.",
            "Pattern-based; a pass does not prove that no personal information is present."),
    "injection": ("Instruction-like text", "medium",
                  "Text written to instruct an AI could manipulate automated pipelines.",
                  "Phrase patterns; reported by location only."),
    "input": ("Input", "high", "The input could not be read or the question was incomplete.", ""),
}
MATERIALITY = {"BLOCKED": "high", "INSUFFICIENT_EVIDENCE": "high", "CONDITIONAL": "medium"}
EFFECT = {
    "BLOCKED": "The data can't support this question as asked.",
    "INSUFFICIENT_EVIDENCE": "This can't be confirmed, so the data does not pass for this question.",
    "CONDITIONAL": "Usable for this question only after the next step is taken and reported.",
}
# Pattern-based rules are less certain than counts.
RULE_CONFIDENCE = {"SCOPE-002": "medium", "LEAK-002": "medium", "PHI-001": "medium", "INJ-001": "medium"}


def _rows_affected(check: str, m: dict, n_cohort: int | None) -> str:
    n = n_cohort or 0
    if check == "completeness":
        r = max(m.get("max_feature_missing_rate") or 0, m.get("outcome_missing_rate") or 0)
        return f"about {round(r * n)} of {n} records"
    if check == "outcome_events":
        return f"{m.get('n_events')} events, {m.get('n_nonevents')} non-events"
    if check == "temporal":
        cov = m.get("horizon_coverage")
        return f"about {round((1 - cov) * n)} of {n} records not followed to the horizon" if cov is not None else ""
    if check == "units":
        return f"{m.get('n_patients_repeated')} patients across {m.get('n_rows')} rows"
    if check == "subgroups":
        return "; ".join(m.get("small_subgroups") or m.get("missing_subgroup_columns") or [])
    if check == "consistency":
        return f"{m.get('n_rows_disagreeing')} records disagree"
    if check == "plausibility":
        return f"{m.get('n_rows_out_of_range')} records"
    if check == "phi":
        return ", ".join(m.get("phi_columns") or [])
    if check == "leakage":
        return ", ".join((m.get("empirically_leaky_features") or []) + (m.get("declared_post_index_features") or []))
    if check == "injection":
        return ", ".join(m.get("injection_locations") or [])
    if check == "cohort":
        return f"{m.get('n_cohort')} of {m.get('n_total')} records"
    if check == "columns":
        return ", ".join(m.get("missing_features") or []) or "whole question"
    return "whole dataset" if check in {"metadata", "phi"} else "whole question"


def _uncertainty(f: dict, m: dict) -> tuple[str, bool]:
    """A 95% range for each measured rate, and whether that range crosses the rule's threshold."""
    ci = m.get("ci") or {}
    parts, borderline = [], False
    for metric, value in (f.get("measured") or {}).items():
        rng = ci.get(metric)
        if not rng or value is None:
            continue
        parts.append(f"{metric} = {value:.1%} (95% range {rng[0]:.1%} to {rng[1]:.1%})")
        for c in (f.get("_conditions") or []):
            if c["metric"] == metric and isinstance(c["value"], (int, float)) and rng[0] <= c["value"] <= rng[1]:
                borderline = True
    if borderline:
        parts.append("the range crosses the rule's threshold, so this finding is borderline")
    return "; ".join(parts), borderline


def enrich(findings: list[dict], checks: list[dict], policy_version: str, dataset_label: str) -> list[dict]:
    by = {c["check"]: c for c in checks}
    n_cohort = (by.get("cohort", {}).get("metrics") or {}).get("n_cohort")
    out = []
    for i, f in enumerate(findings, 1):
        label, conf, why, limit = CHECKS.get(f["check"], (f["check"], "medium", "", ""))
        m = (by.get(f["check"], {}) or {}).get("metrics") or {}
        measured = ", ".join(f"{k} = {v}" for k, v in (f.get("measured") or {}).items())
        effect = (f"Accepted by the question card as: {f['accepted_as']}. Recorded, not counted against the verdict."
                  if f.get("accepted") else f"{why} {EFFECT.get(f['verdict'], '')}".strip())
        unc, borderline = _uncertainty(f, m)
        out.append({**{k: v for k, v in f.items() if k != "_conditions"},
                    "uncertainty": unc or "Exact count; no sampling uncertainty applies to this check.",
                    "borderline": borderline,
                    "finding_id": f"F{i}",
                    "check_performed": label,
                    "fields_used": f.get("fields_used") or (by.get(f["check"], {}) or {}).get("fields", []),
                    "rows_or_groups_affected": _rows_affected(f["check"], m, n_cohort),
                    "effect_on_intended_use": effect,
                    "materiality": "low" if f.get("accepted") else MATERIALITY.get(f["verdict"], "low"),
                    "confidence": RULE_CONFIDENCE.get(f["rule_id"], conf),
                    "evidence_or_source": (f"Measured {measured}. Rule {f['rule_id']} ({f.get('rule_condition', '')}), "
                                           f"policy v{policy_version}, on {dataset_label}."),
                    "limitation": limit,
                    "needs_human_review": True})
    return out


TEMPLATE_COLUMNS = ["finding_id", "check_performed", "fields_used", "rows_or_groups_affected", "what_was_found",
                    "effect_on_intended_use", "materiality(high|medium|low|none)", "confidence(high|medium|low)",
                    "evidence_or_source", "limitation", "recommended_next_step", "needs_human_review(yes|no)"]


def template_csv(findings: list[dict]) -> str:
    """The event's findings_template.csv columns, one row per finding."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(TEMPLATE_COLUMNS)
    for f in findings:
        w.writerow([f["finding_id"], f["check_performed"], "; ".join(f["fields_used"]), f["rows_or_groups_affected"],
                    f"[{f['rule_id']}] {f['reason']}", f["effect_on_intended_use"], f["materiality"], f["confidence"],
                    f["evidence_or_source"], f["limitation"],
                    f"{f['remedy']} To reconsider: {f.get('reconsider', '')}".strip(),
                    "yes" if f["needs_human_review"] else "no"])
    return buf.getvalue()


VERDICT_SENTENCE = {
    "READY": "The data can support this question as stated.",
    "CONDITIONAL": "The data can support this question only after the steps below are taken and reported.",
    "BLOCKED": "The data can't support this question as asked.",
    "INSUFFICIENT_EVIDENCE": "The tool can't confirm something this question needs, so the data doesn't pass.",
}
ORDER = {"BLOCKED": 0, "INSUFFICIENT_EVIDENCE": 1, "CONDITIONAL": 2}


def _size(f: dict) -> int:
    import re
    m = re.search(r"(\d[\d,]*)", f.get("rows_or_groups_affected") or "")
    return int(m.group(1).replace(",", "")) if m else 0


def summarize(verdict: str, findings: list[dict], n_cohort: int | None, accepted: list[dict]) -> dict:
    """Plain-English summary and next steps, most serious and largest first."""
    counted = [f for f in findings if not f.get("accepted")]
    ranked = sorted(counted, key=lambda f: (ORDER.get(f["verdict"], 3), -_size(f)))
    head = VERDICT_SENTENCE[verdict]
    group = f" {n_cohort:,} records match the group being studied." if n_cohort is not None else ""
    if ranked:
        issues = " ".join(f["reason"].rstrip(".") + "." for f in ranked[:2])
        more = f" There are {len(ranked) - 2} more issue(s) below." if len(ranked) > 2 else ""
        body = f" What needs attention: {issues}{more}"
    else:
        body = " No check found a problem for this question."
    acc = (f" The question card accepts {len(accepted)} limitation(s), which a reviewer must confirm."
           if accepted else "")
    steps = [{"rank": i, "rule_id": f["rule_id"], "verdict": f["verdict"], "action": f["remedy"],
              "size": f.get("rows_or_groups_affected", ""), "unblocks": f["verdict"] != "CONDITIONAL",
              "evidence_to_reconsider": f.get("reconsider", "")}
             for i, f in enumerate(ranked, 1)]
    return {"plain_summary": head + group + body + acc + " A person must review before use.",
            "next_steps": steps}
