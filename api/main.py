"""FastAPI service for the Cohort Firewall.

Run:  uvicorn api.main:app --reload --port 8000
Docs: http://localhost:8000/docs

Raw uploads are evaluated in memory and never persisted. Only hashes, the spec,
findings and the certificate are stored (Supabase, optional).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cohort_firewall import certificate
from cohort_firewall.engine import DEFAULT_POLICY, evaluate_dataset

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Cohort Firewall", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CF_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"], allow_headers=["*"],
)


def _store(result: dict) -> None:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return
    from supabase import create_client  # optional dependency
    cert = result["certificate"]
    create_client(url, key).table("runs").insert({
        "cert_id": cert["cert_id"],
        "verdict": result["verdict"],
        "question_text": (result.get("spec") or {}).get("question_text"),
        "spec": result.get("spec"),
        "findings": result["findings"],
        "checks": result["checks"],
        "certificate": cert,
        "dataset_sha256": cert["payload"]["dataset_sha256"],
        "policy_version": result["policy_version"],
    }).execute()


@app.post("/evaluate")
async def evaluate(
    dataset: UploadFile = File(..., description="CSV file"),
    dictionary: UploadFile | None = File(None, description="Data dictionary JSON"),
    spec: str | None = Form(None, description="QuestionSpec as JSON (skips the LLM parser)"),
    question: str | None = Form(None, description="Free-text question (used with use_llm_parser)"),
    use_llm_parser: bool = Form(False),
    use_llm_report: bool = Form(False),
):
    data = await dataset.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Dataset too large for this prototype.")
    dct = None
    if dictionary is not None:
        try:
            dct = json.loads(await dictionary.read())
        except json.JSONDecodeError:
            dct = None  # treated as "no dictionary" -> INSUFFICIENT_EVIDENCE, never a crash
    spec_obj = None
    if spec:
        try:
            spec_obj = json.loads(spec)
        except json.JSONDecodeError:
            spec_obj = {"question_text": question or "", "_error": "spec was not valid JSON"}
    result = evaluate_dataset(data, dct, spec=spec_obj, question=question,
                              use_llm_parser=use_llm_parser, use_llm_report=use_llm_report)
    try:
        _store(result)
    except Exception:
        result["storage_warning"] = "Run was evaluated but not stored."
    return result


class VerifyRequest(BaseModel):
    certificate: dict


@app.post("/verify")
def verify(req: VerifyRequest):
    return {"valid": certificate.verify(req.certificate)}


@app.get("/public-key")
def public_key():
    return {"alg": "Ed25519", "pem": certificate.public_key_pem()}


@app.get("/policy")
def policy():
    """The active rules, published so anyone can see exactly what decides a verdict."""
    return {"yaml": Path(DEFAULT_POLICY).read_text()}


@app.get("/health")
def health():
    return {"ok": True}
