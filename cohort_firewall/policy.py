"""Policy engine: map check metrics to a verdict using a versioned YAML rule file.

No eval(): conditions are (metric, op, value) triples.
Default-deny: a check that could not run, a check that never reported, or a rule that
references a metric its check did not produce all yield INSUFFICIENT_EVIDENCE.
"""
from __future__ import annotations

import hashlib
import operator
from dataclasses import dataclass
from pathlib import Path

import yaml

from .checks import ALL_CHECKS, CheckResult

PRECEDENCE = ["BLOCKED", "INSUFFICIENT_EVIDENCE", "CONDITIONAL", "READY"]
OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge,
       "<": operator.lt, "<=": operator.le}
EXPECTED_CHECKS = {fn.__name__.removeprefix("check_") for fn in ALL_CHECKS}


@dataclass
class Policy:
    version: str
    parameters: dict
    rules: list[dict]
    sha256: str
    acceptable: dict | None = None

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw)
        return cls(doc["version"], doc.get("parameters", {}), doc["rules"],
                   hashlib.sha256(raw).hexdigest(), doc.get("acceptable", {}) or {})


class _Fmt(dict):
    def __missing__(self, k):
        return "?"


def _fmt(template: str, metrics: dict) -> str:
    vals = {k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in metrics.items()}
    try:
        return template.format_map(_Fmt(vals))
    except (ValueError, TypeError):  # e.g. a format spec applied to a None/str value
        return template


def evaluate(results: list[CheckResult], policy: Policy, expected: set[str] | None = None,
             accepted: set[str] | None = None) -> dict:
    by_name = {r.check: r for r in results}
    findings = []
    expected = EXPECTED_CHECKS if expected is None else expected

    for name in sorted(expected - set(by_name)):
        findings.append({"rule_id": "DEFAULT-DENY", "check": name, "verdict": "INSUFFICIENT_EVIDENCE",
                         "reason": f"Check '{name}' did not report.", "remedy": "Investigate the engine."})
    for r in results:
        if r.status == "not_evaluable":
            findings.append({"rule_id": "DEFAULT-DENY", "check": r.check, "verdict": "INSUFFICIENT_EVIDENCE",
                             "reason": f"Check '{r.check}' could not be evaluated. {r.note}".strip(),
                             "remedy": "Supply the missing data or metadata this check needs."})

    for rule in policy.rules:
        r = by_name.get(rule["check"])
        if r is None or r.status != "ok":
            continue  # already covered by DEFAULT-DENY or skipped (not applicable)
        fired, broken = True, False
        for cond in rule["when"]:
            if cond["metric"] not in r.metrics:
                broken = True
                break
            v = r.metrics[cond["metric"]]
            if v is None:
                fired = False
                break
            if not OPS[cond["op"]](v, cond["value"]):
                fired = False
                break
        if broken:
            findings.append({"rule_id": rule["id"], "check": rule["check"], "verdict": "INSUFFICIENT_EVIDENCE",
                             "reason": f"Rule {rule['id']} references a metric the check did not produce.",
                             "remedy": "Fix the rule/engine mismatch."})
        elif fired:
            findings.append({"rule_id": rule["id"], "check": rule["check"], "verdict": rule["verdict"],
                             "reason": _fmt(rule["reason"], r.metrics),
                             "remedy": _fmt(rule.get("remedy", ""), r.metrics)})

    accepted = set(accepted or set())
    allowed = set((policy.acceptable or {}).keys())
    ignored_acceptances = sorted(accepted - allowed)
    for f in findings:
        if f["rule_id"] in accepted and f["rule_id"] in allowed and f["verdict"] == "CONDITIONAL":
            f["accepted"] = True
            f["accepted_as"] = policy.acceptable[f["rule_id"]]

    verdict = "READY"
    counted = [f for f in findings if not f.get("accepted")]
    for v in PRECEDENCE:
        if any(f["verdict"] == v for f in counted):
            verdict = v
            break
    findings.sort(key=lambda f: (PRECEDENCE.index(f["verdict"]), bool(f.get("accepted"))))
    return {"verdict": verdict, "findings": findings, "ignored_acceptances": ignored_acceptances}
