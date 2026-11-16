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
from cohort_firewall import datasets, ledger
from cohort_firewall.policy import Policy
from cohort_firewall.review import ReviewError, review_question, review_release, reviews_for, verify_review
from cohort_firewall.tower.run import list_releases, release_folders, run_tower

CHALLENGE_REPO = Path(os.environ.get("CF_CHALLENGE_REPO", "~/oncosys-hackathon-challenge")).expanduser()
TOWER_OUT = Path(__file__).resolve().parent.parent / "outputs"

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
    result["x_ledger"] = _log_question(result)
    return result


def _log_question(r: dict) -> dict:
    c = r.get("certificate") or {}
    return ledger.append("question_check", {
        "cert_id": c.get("cert_id"), "verdict": r.get("verdict"),
        "rules": [f["rule_id"] for f in r.get("findings", [])],
        "dataset_sha256": (c.get("payload") or {}).get("dataset_sha256")})


def _log_release(doc: dict) -> dict:
    c = doc.get("certificate") or {}
    return ledger.append("release_check", {
        "cert_id": c.get("cert_id"), "verdict": doc.get("verdict"),
        "releases": [r["name"] for r in doc["data"]["releases"]],
        "analyses": {a["id"]: a["verdict"] for a in doc.get("analyses", [])},
        "findings": len(doc.get("findings", [])),
        "dataset_sha256": (c.get("payload") or {}).get("dataset_sha256")})


@app.get("/ledger")
def get_ledger(limit: int = 10):
    entries = ledger.read_all()[-max(1, min(limit, 50)):]
    return {"verify": ledger.verify(), "recent": [
        {k: e[k] for k in ("seq", "ts", "event", "subject", "hash")} for e in reversed(entries)]}


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


@app.get("/tower/releases")
def tower_releases():
    """Releases found in the challenge repo's data/tcga-brca/releases/ folder."""
    return {"challenge_repo": str(CHALLENGE_REPO), "releases": list_releases(CHALLENGE_REPO)}


class TowerRequest(BaseModel):
    release: str
    include_rna: bool = True
    include_summaries: bool = True
    summaries_in_findings: bool = False


@app.post("/tower/run")
def tower_run(req: TowerRequest):
    folders = release_folders(CHALLENGE_REPO)
    if req.release not in folders:   # only listed folders: no arbitrary paths from the browser
        raise HTTPException(404, f"Unknown release '{req.release}'. Open an envelope, or put the folder "
                                 "under data/tcga-brca/releases/.")
    path_b = folders[req.release]
    try:
        doc = run_tower(CHALLENGE_REPO, path_b, include_rna=req.include_rna,
                        include_summaries=req.include_summaries, summaries_in_findings=req.summaries_in_findings)
    except FileNotFoundError as e:
        raise HTTPException(400, f"Missing input: {e}. Run fetch.py in the challenge repo first.")
    TOWER_OUT.mkdir(exist_ok=True)
    doc["x_ledger"] = _log_release(doc)
    (TOWER_OUT / f"findings-{req.release.replace(' ', '-')}.json").write_text(json.dumps(doc, indent=2))
    return doc


class UnsealRequest(BaseModel):
    envelope: str
    code: str


@app.post("/tower/unseal")
def tower_unseal(req: UnsealRequest):
    """Open a sealed envelope with the organizers' own envelopes/unseal.py, then report its release."""
    import re
    import subprocess
    import sys
    env = req.envelope.strip()
    words = req.code.replace("-", " ").split()
    if not re.fullmatch(r"(?i)practice|E?\d{1,2}", env):
        raise HTTPException(400, "Envelope must be a number like 07, or 'practice'.")
    if len(words) != 4 or not all(re.fullmatch(r"[A-Za-z]{2,20}", w) for w in words):
        raise HTTPException(400, "The code is four words, like: amber falcon river quartz.")
    script = CHALLENGE_REPO / "envelopes" / "unseal.py"
    if not script.exists():
        raise HTTPException(400, "envelopes/unseal.py not found. Run git pull in the challenge repo.")
    proc = subprocess.run([sys.executable, str(script), env, *words], cwd=CHALLENGE_REPO,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    log = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        raise HTTPException(400, log.splitlines()[-1].strip(" ✗") if log else "unseal.py failed.")
    name = "envelope " + ("practice" if env.lower() == "practice" else f"E{int(env.lstrip('Ee')):02d}")
    if name not in release_folders(CHALLENGE_REPO):
        raise HTTPException(400, f"Opened, but no release folder was found. Output: {log[-300:]}")
    ledger.append("envelope_opened", {"envelope": name})
    return {"name": name, "log": log}


class BuildRequest(BaseModel):
    config: dict


@app.post("/tower/build")
def tower_build(req: BuildRequest):
    """Build a release from a make_release.py config, using the event's own script, for live tests."""
    import re
    import subprocess
    import sys
    cfg = req.config
    name = str(cfg.get("name", ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise HTTPException(400, "Config 'name' must be letters, digits, '-' or '_' (it becomes a folder name).")
    if name in {"raw", "practice-B"}:
        raise HTTPException(400, f"'{name}' is protected; choose another release name.")
    if not isinstance(cfg.get("changes"), list) or "seed" not in cfg:
        raise HTTPException(400, "Config needs 'name', 'seed' and a 'changes' list (see make_release.py).")
    script = CHALLENGE_REPO / "data" / "tcga-brca" / "make_release.py"
    if not script.exists():
        raise HTTPException(400, f"make_release.py not found under {CHALLENGE_REPO}.")
    cfg_dir = TOWER_OUT / "configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / f"{name}.json"
    cfg_path.write_text(json.dumps(cfg, indent=2))
    proc = subprocess.run([sys.executable, str(script), "--config", str(cfg_path)], cwd=CHALLENGE_REPO,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if proc.returncode != 0:
        raise HTTPException(400, f"make_release.py failed: {(proc.stderr or proc.stdout).strip()[-500:]}")
    # CHANGES.json (the answer key) is written by the script but never read or returned here.
    return {"name": name, "log": proc.stdout.strip()}


@app.get("/datasets")
def list_datasets():
    return {"datasets": [{"id": d["id"], "label": d["label"]} for d in datasets.available()]}


@app.get("/datasets/{dataset_id}")
def describe_dataset(dataset_id: str):
    try:
        return datasets.describe(dataset_id)
    except KeyError:
        raise HTTPException(404, f"Unknown dataset '{dataset_id}'. Run data/flatten_tcga.py for TCGA.")


@app.get("/policy/acceptable")
def acceptable_limitations():
    """Limitations a question card may accept (Conditional rules only), from the policy file."""
    p = Policy.load(DEFAULT_POLICY)
    return {"policy_version": p.version, "acceptable": [{"rule_id": k, "label": v} for k, v in p.acceptable.items()]}


@app.get("/examples/cards/{dataset_id}")
def example_cards(dataset_id: str):
    """Example research-question cards for a dataset, to start the form from."""
    prefix = {"tcga_brca_raw": "tcga_", "demo_breast_cohort": "q"}.get(dataset_id)
    if prefix is None:
        raise HTTPException(404, "No examples for this dataset.")
    folder = Path(__file__).resolve().parent.parent / "examples" / "specs"
    out = [{"id": p.stem, "spec": json.loads(p.read_text())} for p in sorted(folder.glob(f"{prefix}*.json"))]
    return {"cards": out}


class CardRequest(BaseModel):
    dataset_id: str
    spec: dict


@app.post("/evaluate-card")
def evaluate_card(req: CardRequest):
    """Check a server-side dataset against a research-question card built in the form."""
    d = datasets.get(req.dataset_id)
    if d is None:
        raise HTTPException(404, f"Unknown dataset '{req.dataset_id}'.")
    result = evaluate_dataset(d["csv"].read_bytes(), json.loads(d["dictionary"].read_text()), spec=req.spec)
    result["x_ledger"] = _log_question(result)
    return result


class QuestionReview(BaseModel):
    result: dict
    reviewer: str
    role: str = ""
    decision: str
    acknowledged: list[str] = []
    note: str = ""


@app.post("/review/question")
def post_question_review(req: QuestionReview):
    try:
        rec = review_question(req.result, req.reviewer, req.role, req.decision, req.acknowledged, req.note)
        r = rec["review"]
        rec["ledger"] = ledger.append("review", {"review_id": r["review_id"], "cert_id": r["subject"]["cert_id"],
                                                 "decision": r["decision"], "reviewer": r["reviewer"]["name"]})
        return rec
    except ReviewError as e:
        raise HTTPException(400, str(e))


class ReleaseReview(BaseModel):
    findings: dict
    reviewer: str
    role: str = ""
    decisions: dict[str, str]
    acknowledged: list[str] = []
    note: str = ""


@app.post("/review/release")
def post_release_review(req: ReleaseReview):
    try:
        rec = review_release(req.findings, req.reviewer, req.role, req.decisions, req.acknowledged, req.note)
        r = rec["review"]
        rec["ledger"] = ledger.append("review", {"review_id": r["review_id"], "cert_id": r["subject"]["cert_id"],
                                                 "decision": {d["analysis"]: d["decision"] for d in r["decisions"]},
                                                 "reviewer": r["reviewer"]["name"]})
        return rec
    except ReviewError as e:
        raise HTTPException(400, str(e))


@app.get("/reviews/{cert_id}")
def get_reviews(cert_id: str):
    import re
    if not re.fullmatch(r"[0-9a-f]{16}", cert_id):
        raise HTTPException(400, "Invalid certificate id.")
    return {"reviews": [{**r, "valid": verify_review(r)} for r in reviews_for(cert_id)]}


@app.get("/health")
def health():
    return {"ok": True}
