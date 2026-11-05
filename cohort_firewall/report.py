"""Readiness report. Deterministic by default; optional LLM wording with output checks."""
from __future__ import annotations

LABELS = {"READY": "Ready", "CONDITIONAL": "Conditional", "BLOCKED": "Blocked",
          "INSUFFICIENT_EVIDENCE": "Insufficient Evidence"}


def template_report(evaluation: dict, question: str) -> str:
    v = evaluation["verdict"]
    lines = [f"**Verdict: {LABELS[v]}** for the question: \"{question}\"", ""]
    if not evaluation["findings"]:
        lines.append("Every applicable check passed under the current policy.")
        return "\n".join(lines)
    lines.append("Why:")
    for f in evaluation["findings"]:
        lines.append(f"- [{f['rule_id']}] ({LABELS[f['verdict']]}) {f['reason']}")
    remedies = [f for f in evaluation["findings"] if f.get("remedy")]
    if remedies:
        lines += ["", "To make this dataset ready for this question:"]
        seen = set()
        for f in remedies:
            if f["remedy"] not in seen:
                seen.add(f["remedy"])
                lines.append(f"- [{f['rule_id']}] {f['remedy']}")
    return "\n".join(lines)


def report_passes_guard(text: str, evaluation: dict) -> bool:
    """LLM wording is accepted only if it keeps the verdict and every non-Ready rule id."""
    if LABELS[evaluation["verdict"]].lower() not in text.lower():
        return False
    for f in evaluation["findings"]:
        if f["verdict"] in {"BLOCKED", "INSUFFICIENT_EVIDENCE"} and f"[{f['rule_id']}]" not in text:
            return False
    other = [l for k, l in LABELS.items() if k != evaluation["verdict"]]
    first_line = text.strip().splitlines()[0].lower() if text.strip() else ""
    return not any(f"verdict: {o.lower()}" in first_line for o in other)


def build_report(evaluation: dict, question: str, use_llm: bool = False) -> dict:
    if use_llm:
        try:
            from .llm import write_report_llm
            text = write_report_llm(evaluation, question)
            if report_passes_guard(text, evaluation):
                return {"text": text, "source": "llm"}
        except Exception:
            pass
    return {"text": template_report(evaluation, question), "source": "template"}
