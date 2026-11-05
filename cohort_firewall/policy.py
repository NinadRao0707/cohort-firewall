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

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        raw = Path(path).read_bytes()
        doc = yaml.safe_load(raw)
        return cls(doc["version"], doc.get("parameters", {}), doc["rules"],
                   hashlib.sha256(raw).hexdigest())


class _Fmt(dict):
    def __missing__(self, k):
        return "?"


def _fmt(template: str, metrics: dict) -> str:
    vals = {k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in metrics.items()}
    try:
        return template.format_map(_Fmt(vals))
    except (ValueError, TypeError):  # e.g. a format spec applied to a None/str value
        return template


def evaluate(results: list[CheckResult], policy: Policy) -> dict:
    by_name = {r.check: r for r in results}
    findings = []

    for name in sorted(EXPECTED_CHECKS - set(by_name)):
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

    verdict = "READY"
    for v in PRECEDENCE:
        if any(f["verdict"] == v for f in findings):
            verdict = v
            break
    findings.sort(key=lambda f: PRECEDENCE.index(f["verdict"]))
    return {"verdict": verdict, "findings": findings}
