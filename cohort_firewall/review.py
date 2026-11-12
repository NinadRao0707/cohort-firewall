"""The human review step: a person records a decision on a result, and the record is signed.

A review can only be attached to a genuine result: the result's certificate must verify, and the
verdict being reviewed is taken from the signed certificate, never from what the browser sends.
Approval is impossible for Blocked or Insufficient Evidence results, and approving a Conditional
result requires acknowledging every finding behind it and writing a note.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import certificate as cert

LABEL = {"Ready": "READY", "Conditional": "CONDITIONAL", "Blocked": "BLOCKED",
         "Insufficient Evidence": "INSUFFICIENT_EVIDENCE"}
ALLOWED = {
    "READY": {"approve", "reject", "request_more"},
    "CONDITIONAL": {"approve_with_conditions", "reject", "request_more"},
    "BLOCKED": {"reject", "request_more"},
    "INSUFFICIENT_EVIDENCE": {"reject", "request_more"},
}
APPROVALS = {"approve", "approve_with_conditions"}
REVIEWS = Path(__file__).resolve().parents[1] / "outputs" / "reviews"


class ReviewError(ValueError):
    pass


def tower_binding(question: str, analyses: list[dict]) -> str:
    """What a Control Tower certificate's spec hash covers: the question and each analysis verdict."""
    return json.dumps({"question": question,
                       "analyses": [{"id": a["id"], "verdict": a["verdict"]} for a in analyses]},
                      sort_keys=True, separators=(",", ":"))


def _check_one(verdict: str, decision: str, required: set[str], acknowledged: set[str], note: str, who: str):
    if decision not in ALLOWED[verdict]:
        raise ReviewError(f"'{decision}' is not allowed for a {verdict.replace('_', ' ').title()} result. "
                          f"Allowed: {', '.join(sorted(ALLOWED[verdict]))}.")
    if decision in APPROVALS and not required <= acknowledged:
        missing = ", ".join(sorted(required - acknowledged))
        raise ReviewError(f"{who}: approving requires confirming you reviewed the evidence for {missing}.")
    if (decision != "approve" or required) and len(note.strip()) < 10:
        raise ReviewError(f"{who}: write a short note (why the findings are acceptable, what conditions apply, "
                          "or what evidence is needed).")


def _sign(payload: dict) -> dict:
    sig = cert._load_key().sign(cert.canonical(payload))
    return {"review": payload, "signature": base64.b64encode(sig).decode(), "alg": "Ed25519"}


def verify_review(record: dict) -> bool:
    from cryptography.hazmat.primitives import serialization
    pub = serialization.load_pem_public_key(cert.public_key_pem().encode())
    try:
        pub.verify(base64.b64decode(record["signature"]), cert.canonical(record["review"]))
        return True
    except Exception:
        return False


def review_question(result: dict, reviewer: str, role: str, decision: str,
                    acknowledged: list[str], note: str) -> dict:
    c = result.get("certificate") or {}
    if not cert.verify(c):
        raise ReviewError("The result's certificate does not verify; it may have been edited.")
    if not reviewer.strip():
        raise ReviewError("Enter the reviewer's name.")
    verdict = c["payload"]["verdict"]
    required = set(c["payload"].get("rule_ids", []))
    _check_one(verdict, decision, required, set(acknowledged), note, "This result")
    payload = {
        "review_id": uuid.uuid4().hex[:12], "type": "question",
        "subject": {"cert_id": c["cert_id"], "verdict": verdict,
                    "question": (result.get("spec") or {}).get("question_text"),
                    "dataset_sha256": c["payload"]["dataset_sha256"],
                    "policy_version": c["payload"]["policy_version"]},
        "reviewer": {"name": reviewer.strip()[:80], "role": role.strip()[:80]},
        "decision": decision, "acknowledged_findings": sorted(set(acknowledged) & required),
        "note": note.strip()[:2000],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return _save(_sign(payload))


def review_release(doc: dict, reviewer: str, role: str, decisions: dict[str, str],
                   acknowledged: list[str], note: str) -> dict:
    c = doc.get("certificate") or {}
    if not cert.verify(c):
        raise ReviewError("The findings' certificate does not verify; it may have been edited.")
    analyses = doc.get("analyses") or []
    bound = hashlib.sha256(tower_binding(doc.get("question", ""), analyses).encode()).hexdigest()
    if bound != c["payload"]["spec_sha256"]:
        raise ReviewError("The analysis verdicts do not match the signed record; they may have been edited.")
    if not reviewer.strip():
        raise ReviewError("Enter the reviewer's name.")
    finding_ids = {f["id"] for f in doc.get("findings", [])}
    per = []
    for a in analyses:
        d = decisions.get(a["id"])
        if not d:
            raise ReviewError(f"Choose a decision for {a['id']}.")
        required = set(a.get("affected_by", [])) & finding_ids
        _check_one(LABEL[a["verdict"]], d, required, set(acknowledged), note, a["id"])
        per.append({"analysis": a["id"], "verdict": a["verdict"], "decision": d})
    payload = {
        "review_id": uuid.uuid4().hex[:12], "type": "release",
        "subject": {"cert_id": c["cert_id"], "overall_verdict": c["payload"]["verdict"],
                    "releases": [r["name"] for r in doc["data"]["releases"]],
                    "policy_version": c["payload"]["policy_version"]},
        "reviewer": {"name": reviewer.strip()[:80], "role": role.strip()[:80]},
        "decisions": per, "acknowledged_findings": sorted(set(acknowledged) & finding_ids),
        "note": note.strip()[:2000],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return _save(_sign(payload))


def _save(record: dict) -> dict:
    REVIEWS.mkdir(parents=True, exist_ok=True)
    r = record["review"]
    (REVIEWS / f"{r['subject']['cert_id']}-{r['review_id']}.json").write_text(json.dumps(record, indent=2))
    return record


def reviews_for(cert_id: str) -> list[dict]:
    if not REVIEWS.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(REVIEWS.glob(f"{cert_id}-*.json"))]
