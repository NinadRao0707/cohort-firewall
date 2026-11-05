"""Readiness certificates: a signed, reproducible record of one verdict.

The certificate binds the exact dataset bytes, dictionary, question spec, policy file and
engine version to the verdict. Anyone holding the public key can verify it was not edited.
Signing uses Ed25519 (cryptography package). For the hackathon a dev key is generated
locally if CF_SIGNING_KEY_PATH is not set; never commit the private key.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import ENGINE_VERSION

DEV_KEY = Path(__file__).resolve().parent.parent / "keys" / "dev_ed25519.pem"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def _load_key() -> Ed25519PrivateKey:
    path = Path(os.environ.get("CF_SIGNING_KEY_PATH", DEV_KEY))
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                           serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
        os.chmod(path, 0o600)
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def public_key_pem() -> str:
    return _load_key().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def issue(*, dataset_bytes: bytes, dictionary: dict | None, spec_json: str,
          policy_version: str, policy_sha256: str, verdict: str, rule_ids: list[str]) -> dict:
    payload = {
        "cert_format": "cohort-firewall/1",
        "engine_version": ENGINE_VERSION,
        "policy_version": policy_version,
        "policy_sha256": policy_sha256,
        "dataset_sha256": sha256_bytes(dataset_bytes),
        "dictionary_sha256": sha256_bytes(canonical(dictionary)) if dictionary else None,
        "spec_sha256": sha256_bytes(spec_json.encode()),
        "verdict": verdict,
        "rule_ids": sorted(set(rule_ids)),
        "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    sig = _load_key().sign(canonical(payload))
    return {
        "cert_id": sha256_bytes(canonical(payload))[:16],
        "payload": payload,
        "signature": base64.b64encode(sig).decode(),
        "alg": "Ed25519",
    }


def verify(cert: dict, public_pem: str | None = None) -> bool:
    pem = (public_pem or public_key_pem()).encode()
    pub: Ed25519PublicKey = serialization.load_pem_public_key(pem)
    try:
        pub.verify(base64.b64decode(cert["signature"]), canonical(cert["payload"]))
        return cert["cert_id"] == sha256_bytes(canonical(cert["payload"]))[:16]
    except Exception:
        return False
