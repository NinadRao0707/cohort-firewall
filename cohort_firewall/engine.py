"""End-to-end evaluation: (dataset, dictionary, question) -> verdict, findings, report, certificate."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from . import ENGINE_VERSION
from .certificate import issue
from .checks import run_checks
from .policy import Policy, evaluate
from .report import build_report
from .spec import SpecError, spec_from_dict

DEFAULT_POLICY = Path(__file__).resolve().parent.parent / "rules" / "policy_v0_1.yaml"


def evaluate_dataset(dataset_bytes: bytes, dictionary: dict | None, spec: dict | None = None,
                     question: str | None = None, policy_path: str | Path = DEFAULT_POLICY,
                     use_llm_parser: bool = False, use_llm_report: bool = False) -> dict:
    policy = Policy.load(policy_path)

    tokens = [str(t) for t in policy.parameters.get("missing_tokens", [])]
    notes: list[str] = []
    try:
        raw = pd.read_csv(io.BytesIO(dataset_bytes), dtype=str, keep_default_na=False)
        placeholder = [t for t in tokens if t.strip()]
        hits = raw.isin(placeholder).sum() if placeholder else pd.Series(dtype=int)
        n_tokens = int(hits.sum())
        token_cols = [str(c) for c in hits[hits > 0].sort_values(ascending=False).index[:3]]
        df = pd.read_csv(io.BytesIO(dataset_bytes), na_values=tokens, keep_default_na=True)
        if n_tokens:
            from .sanitize import safe_ident
            notes.append(f"{n_tokens} placeholder value(s) such as 'NA' or '[Not Available]' were treated as "
                         f"missing (columns: {', '.join(safe_ident(c) for c in token_cols)}).")
    except Exception as e:
        return _short_circuit("DATA-LOAD", f"Dataset could not be read as CSV ({type(e).__name__}).",
                              dataset_bytes, dictionary, spec or {"question_text": question}, policy)

    if spec is None:
        if not (use_llm_parser and question):
            return _short_circuit("SPEC-MISSING", "No question specification supplied.",
                                  dataset_bytes, dictionary, {"question_text": question}, policy)
        try:
            from .llm import parse_question
            spec = parse_question(question, dictionary, list(df.columns))
        except Exception as e:
            return _short_circuit("SPEC-PARSE", f"Question could not be parsed ({type(e).__name__}).",
                                  dataset_bytes, dictionary, {"question_text": question}, policy)
    try:
        qs = spec_from_dict(spec)
    except SpecError as e:
        return _short_circuit("SPEC-INVALID", f"Question specification failed validation: {e}",
                              dataset_bytes, dictionary, spec, policy)

    results = run_checks(df, dictionary, qs, policy.parameters)
    ev = evaluate(results, policy, accepted=set(qs.acceptable_limitations))
    cert = issue(dataset_bytes=dataset_bytes, dictionary=dictionary, spec_json=qs.canonical_json(),
                 policy_version=policy.version, policy_sha256=policy.sha256,
                 verdict=ev["verdict"], rule_ids=[f["rule_id"] for f in ev["findings"]])
    return {
        "verdict": ev["verdict"],
        "human_review": human_review(ev["verdict"], [f for f in ev["findings"] if f.get("accepted")]),
        "accepted_limitations": [{"rule_id": f["rule_id"], "as": f["accepted_as"]}
                                 for f in ev["findings"] if f.get("accepted")],
        "ignored_acceptances": ev.get("ignored_acceptances", []),
        "notes": notes,
        "limitations": LIMITATIONS,
        "findings": ev["findings"],
        "checks": [r.to_dict() for r in results],
        "spec": qs.to_dict(),
        "report": build_report(ev, qs.question_text, use_llm=use_llm_report),
        "certificate": cert,
        "engine_version": ENGINE_VERSION,
        "policy_version": policy.version,
    }


LIMITATIONS = [
    "This is a research data-readiness screen. It is not a clinical tool and makes no claim of "
    "clinical validity, regulatory compliance, or production readiness.",
    "Identifier detection is heuristic. A pass does not guarantee that no personal information is present.",
    "Leakage detection checks one feature at a time and can miss leakage spread across several features.",
    "Thresholds (events per parameter, minimum subgroup size, missingness) are configurable defaults, "
    "not clinical standards.",
    "Subgroup coverage uses minimum counts and does not compare against a reference population.",
]


def human_review(verdict: str, accepted: list | None = None) -> dict:
    if verdict == "READY" and accepted:
        return {"level": "required",
                "text": f"Ready only because the question card accepts {len(accepted)} limitation(s). "
                        "A person must confirm those limitations are acceptable for this use."}
    if verdict == "READY":
        return {"level": "recommended",
                "text": "A person should still confirm the question and data match before training."}
    if verdict == "BLOCKED":
        return {"level": "required",
                "text": "Do not use this dataset for this question. A person must resolve every Blocked finding first."}
    return {"level": "required",
            "text": "A person must review the findings and decide whether the remedies are acceptable."}


def _short_circuit(rule_id, reason, dataset_bytes, dictionary, spec, policy) -> dict:
    ev = {"verdict": "INSUFFICIENT_EVIDENCE",
          "findings": [{"rule_id": rule_id, "check": "input", "verdict": "INSUFFICIENT_EVIDENCE",
                        "reason": reason, "remedy": "Provide a readable dataset and a complete question."}]}
    import json
    spec_json = json.dumps(spec or {}, sort_keys=True, default=str)
    cert = issue(dataset_bytes=dataset_bytes, dictionary=dictionary, spec_json=spec_json,
                 policy_version=policy.version, policy_sha256=policy.sha256,
                 verdict=ev["verdict"], rule_ids=[rule_id])
    q = (spec or {}).get("question_text") or ""
    return {**ev, "human_review": human_review(ev["verdict"]), "notes": [], "limitations": LIMITATIONS,
            "accepted_limitations": [], "ignored_acceptances": [],
            "checks": [], "spec": spec, "report": build_report(ev, q),
            "certificate": cert, "engine_version": ENGINE_VERSION, "policy_version": policy.version}
