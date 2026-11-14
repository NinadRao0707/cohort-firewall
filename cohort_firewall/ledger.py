"""Tamper-evident audit ledger: a hash-chained, signed record of every check and every human decision.

Each entry holds its sequence number, time, event, a short subject (certificate id, verdicts, reviewer),
the previous entry's hash, its own hash, and an Ed25519 signature of that hash. Editing, deleting,
inserting or reordering any past entry breaks the chain, and verify() names the first entry affected.

Limitation: removing entries from the END leaves a valid shorter chain. Record the head hash somewhere
else (the review note, a ticket, an email) to detect that, as Certificate Transparency logs do.

  python -m cohort_firewall.ledger verify
  python -m cohort_firewall.ledger show
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import certificate as cert

GENESIS = "0" * 64
_lock = threading.Lock()


def path() -> Path:
    return Path(os.environ.get("CF_LEDGER_PATH",
                               Path(__file__).resolve().parents[1] / "outputs" / "ledger.jsonl"))


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k not in ("hash", "sig")}
    return hashlib.sha256(cert.canonical(body)).hexdigest()


def read_all(p: Path | None = None) -> list[dict]:
    p = p or path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def append(event: str, subject: dict) -> dict:
    """Add one entry and return {seq, hash}. Never raises: the ledger must not break a check."""
    try:
        with _lock:
            p = path()
            p.parent.mkdir(parents=True, exist_ok=True)
            last = None
            if p.exists():
                lines = [x for x in p.read_text().splitlines() if x.strip()]
                last = json.loads(lines[-1]) if lines else None
            entry = {"seq": (last["seq"] + 1) if last else 1,
                     "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "event": event, "subject": subject,
                     "prev": last["hash"] if last else GENESIS}
            entry["hash"] = _hash(entry)
            entry["sig"] = base64.b64encode(cert._load_key().sign(bytes.fromhex(entry["hash"]))).decode()
            with p.open("a") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
            return {"seq": entry["seq"], "hash": entry["hash"]}
    except Exception as e:  # pragma: no cover
        return {"error": f"ledger not written: {e}"}


def verify(p: Path | None = None) -> dict:
    from cryptography.hazmat.primitives import serialization
    pub = serialization.load_pem_public_key(cert.public_key_pem().encode())
    entries, problems = read_all(p), []
    prev = GENESIS
    for i, e in enumerate(entries, 1):
        where = f"entry {i}"
        if e.get("seq") != i:
            problems.append(f"{where}: sequence number is {e.get('seq')}, expected {i} (an entry was removed, added or moved)")
        if e.get("prev") != prev:
            problems.append(f"{where}: does not link to the entry before it (the chain was broken here)")
        if _hash(e) != e.get("hash"):
            problems.append(f"{where}: contents were changed after it was written")
        else:
            try:
                pub.verify(base64.b64decode(e["sig"]), bytes.fromhex(e["hash"]))
            except Exception:
                problems.append(f"{where}: signature does not match (not written by this tool's key)")
        prev = e.get("hash", "")
    return {"ok": not problems, "entries": len(entries), "head": entries[-1]["hash"] if entries else GENESIS,
            "problems": problems[:20]}


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "verify"
    if cmd == "show":
        for e in read_all()[-20:]:
            s = e["subject"]
            print(f"#{e['seq']:<4} {e['ts']}  {e['event']:<15} {s.get('verdict') or s.get('decision') or ''}  "
                  f"{s.get('cert_id', '')}  {e['hash'][:12]}")
        return 0
    r = verify()
    if r["ok"]:
        print(f"Ledger intact: {r['entries']} entries, head {r['head'][:16]}")
        return 0
    print(f"LEDGER BROKEN ({r['entries']} entries):")
    for x in r["problems"]:
        print("  -", x)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
