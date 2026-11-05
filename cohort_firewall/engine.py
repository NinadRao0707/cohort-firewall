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

    try:
        df = pd.read_csv(io.BytesIO(dataset_bytes))
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
    ev = evaluate(results, policy)
    cert = issue(dataset_bytes=dataset_bytes, dictionary=dictionary, spec_json=qs.canonical_json(),
                 policy_version=policy.version, policy_sha256=policy.sha256,
                 verdict=ev["verdict"], rule_ids=[f["rule_id"] for f in ev["findings"]])
    return {
        "verdict": ev["verdict"],
        "findings": ev["findings"],
        "checks": [r.to_dict() for r in results],
        "spec": qs.to_dict(),
        "report": build_report(ev, qs.question_text, use_llm=use_llm_report),
        "certificate": cert,
        "engine_version": ENGINE_VERSION,
        "policy_version": policy.version,
    }


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
    return {**ev, "checks": [], "spec": spec, "report": build_report(ev, q),
            "certificate": cert, "engine_version": ENGINE_VERSION, "policy_version": policy.version}
