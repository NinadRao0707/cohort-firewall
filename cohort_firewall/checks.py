"""Deterministic readiness checks.

Every check returns a CheckResult with:
  status  "ok"            the check ran; metrics are trustworthy
          "not_evaluable" the check could not run (missing column, no metadata...);
                          the policy turns this into INSUFFICIENT_EVIDENCE (default-deny)
          "skipped"       the check does not apply to this question
  metrics flat dict of numbers/bools/short lists the policy rules read

Checks never decide the verdict. They measure; rules/policy_*.yaml decides.
Nothing here calls an LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from .sanitize import looks_like_injection, safe_ident
from .spec import QuestionSpec

CLINICAL_USES = {"clinical_decision_support", "direct_patient_care"}

# Deterministic backstop in case the LLM parser mislabels intended_use.
CLINICAL_PHRASES = [
    r"should (this|the|my|a) patient",
    r"recommend (a |the )?(treatment|therapy|regimen|dose|dosing)",
    r"which (treatment|therapy|drug|regimen) (should|to)",
    r"decide (on )?(treatment|therapy)",
    r"\bfor (my|this) patient\b",
    r"\b(prescribe|dosing for)\b",
    r"triage (patients|this patient)",
]
_CLIN = re.compile("|".join(CLINICAL_PHRASES), re.IGNORECASE)

# HIPAA Safe Harbor-style identifier heuristics (names, geography below state, full dates,
# phone, email, SSN, record numbers...). Heuristic only; a hit means "looks like PHI".
PHI_NAME_HINTS = re.compile(
    r"(^|_)(first|last|middle|maiden)?_?name$|ssn|social_?sec|mrn|medical_?record|phone|"
    r"fax|e_?mail|address|street|^zip|zip_?code|postal|passport|drivers?|license_?no|"
    r"birth_?date|^dob$|date_?of_?birth|ip_?addr|device_?id|account_?(no|num)",
    re.IGNORECASE,
)
PHI_VALUE_PATTERNS = {
    "ssn": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "phone": re.compile(r"^(\+1[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"),
    "full_date": re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}.*)?$|^\d{1,2}/\d{1,2}/\d{4}$"),
    "zip5": re.compile(r"^\d{5}(-\d{4})?$"),
}
ALLOWED_LICENSES = {
    "apache-2.0", "mit", "cc0-1.0", "cc-by-4.0", "cc-by-sa-4.0", "odc-by-1.0",
    "pddl-1.0", "event-approved",
}


@dataclass
class CheckResult:
    check: str
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self):
        return {"check": self.check, "status": self.status, "metrics": self.metrics, "note": self.note}


@dataclass
class Context:
    df: pd.DataFrame | None
    dictionary: dict | None
    spec: QuestionSpec
    params: dict
    cohort: pd.DataFrame | None = None
    features: list[str] = field(default_factory=list)

    @property
    def coldefs(self) -> dict:
        return (self.dictionary or {}).get("columns", {}) or {}


# ---------------------------------------------------------------- helpers

def _resolve_features(ctx: Context) -> list[str]:
    spec = ctx.spec
    if spec.feature_columns != ["*"]:
        return list(spec.feature_columns)
    excluded = {spec.outcome_column, spec.time_column}
    out = []
    for c in ctx.df.columns:
        if c in excluded:
            continue
        role = ctx.coldefs.get(c, {}).get("role")
        if role in {"id", "outcome", "time", "text"}:
            continue
        out.append(c)
    return out


def _apply_filter(df: pd.DataFrame, f) -> pd.Series:
    s = df[f.column]
    ops: dict[str, Callable] = {
        "==": lambda: s == f.value, "!=": lambda: s != f.value,
        ">": lambda: s > f.value, ">=": lambda: s >= f.value,
        "<": lambda: s < f.value, "<=": lambda: s <= f.value,
        "in": lambda: s.isin(f.value if isinstance(f.value, list) else [f.value]),
        "not_in": lambda: ~s.isin(f.value if isinstance(f.value, list) else [f.value]),
    }
    return ops[f.op]()


def _binary_outcome(ctx: Context, frame: pd.DataFrame) -> pd.Series:
    y = frame[ctx.spec.outcome_column]
    return (y == ctx.spec.outcome_positive_value).where(y.notna())


def _auc(x: pd.Series, y: pd.Series) -> float | None:
    """Single-feature ROC AUC via Mann-Whitney ranks; returns max(auc, 1-auc)."""
    m = x.notna() & y.notna()
    x, y = x[m], y[m].astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return None
    if not pd.api.types.is_numeric_dtype(x):
        if x.nunique() > 50:
            return None
        x = x.map(y.groupby(x).mean())  # target-encode low-cardinality categoricals
    r = x.rank(method="average")
    auc = (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    return float(max(auc, 1 - auc))


def _n_parameters(frame: pd.DataFrame, features: list[str]) -> int:
    n = 0
    for c in features:
        s = frame[c]
        if pd.api.types.is_numeric_dtype(s) and s.nunique() > 2:
            n += 1
        else:
            n += max(int(s.nunique()) - 1, 1)
    return n


# ---------------------------------------------------------------- checks

def check_metadata(ctx: Context) -> CheckResult:
    d = ctx.dictionary
    if not d:
        return CheckResult("metadata", "ok", {
            "has_dictionary": False, "license_recognized": False,
            "contains_real_patient_data": None, "has_provenance": False,
            "undocumented_column_share": 1.0,
        }, "No data dictionary supplied.")
    meta = d.get("dataset", {}) or {}
    lic = str(meta.get("license", "")).strip().lower()
    cols = list(ctx.df.columns) if ctx.df is not None else []
    undocumented = [c for c in cols if c not in ctx.coldefs]
    real = meta.get("contains_real_patient_data")
    return CheckResult("metadata", "ok", {
        "has_dictionary": True,
        "license_recognized": lic in ALLOWED_LICENSES,
        "contains_real_patient_data": real if isinstance(real, bool) else None,
        "real_patient_status_declared": isinstance(real, bool),
        "has_provenance": bool(meta.get("source")) and bool(meta.get("provenance")),
        "undocumented_column_share": round(len(undocumented) / len(cols), 3) if cols else 0.0,
        "undocumented_columns": [safe_ident(c) for c in undocumented[:10]],
    })


def check_scope(ctx: Context) -> CheckResult:
    hit = _CLIN.search(ctx.spec.question_text or "")
    return CheckResult("scope", "ok", {
        "clinical_use": ctx.spec.intended_use in CLINICAL_USES,
        "keyword_guard_hit": bool(hit),
        "intended_use": ctx.spec.intended_use,
    })


def check_spec_quality(ctx: Context) -> CheckResult:
    return CheckResult("spec_quality", "ok", {"parse_confidence": ctx.spec.parse_confidence})


def check_columns(ctx: Context) -> CheckResult:
    spec, cols = ctx.spec, set(ctx.df.columns)
    ctx.features = _resolve_features(ctx)
    missing_feats = [c for c in ctx.features if c not in cols]
    missing_filters = [f.column for f in spec.population_filters if f.column not in cols]
    needs_time = spec.task_type == "survival" or spec.time_horizon_months is not None
    return CheckResult("columns", "ok", {
        "outcome_required": spec.outcome_column is not None,
        "outcome_present": spec.outcome_column in cols if spec.outcome_column else True,
        "n_missing_features": len(missing_feats),
        "missing_features": [safe_ident(c) for c in missing_feats],
        "n_missing_filter_columns": len(missing_filters),
        "time_present": (spec.time_column in cols) if needs_time and spec.time_column else (not needs_time),
        "n_features": len(ctx.features),
    })


def check_cohort(ctx: Context) -> CheckResult:
    df = ctx.df
    if any(f.column not in df.columns for f in ctx.spec.population_filters):
        return CheckResult("cohort", "not_evaluable", note="A population filter column is missing.")
    mask = pd.Series(True, index=df.index)
    for f in ctx.spec.population_filters:
        mask &= _apply_filter(df, f).fillna(False).astype(bool)
    ctx.cohort = df[mask]
    return CheckResult("cohort", "ok", {"n_total": int(len(df)), "n_cohort": int(mask.sum())})


def check_completeness(ctx: Context) -> CheckResult:
    if ctx.cohort is None or len(ctx.cohort) == 0:
        return CheckResult("completeness", "not_evaluable", note="Empty or undefined cohort.")
    c = ctx.cohort
    present = [f for f in ctx.features if f in c.columns]
    rates = {f: float(c[f].isna().mean()) for f in present}
    worst = max(rates, key=rates.get) if rates else None
    oc = ctx.spec.outcome_column
    return CheckResult("completeness", "ok", {
        "outcome_missing_rate": round(float(c[oc].isna().mean()), 3) if oc in c.columns else None,
        "max_feature_missing_rate": round(rates[worst], 3) if worst else 0.0,
        "worst_feature": safe_ident(worst) if worst else None,
    })


def check_outcome_events(ctx: Context) -> CheckResult:
    spec = ctx.spec
    if spec.task_type not in {"binary_classification", "survival"}:
        return CheckResult("outcome_events", "skipped")
    c = ctx.cohort
    if c is None or spec.outcome_column not in (c.columns if c is not None else []):
        return CheckResult("outcome_events", "not_evaluable", note="Outcome column unavailable.")
    y = _binary_outcome(ctx, c).dropna().astype(bool)
    events, nonevents = int(y.sum()), int((~y).sum())
    present = [f for f in ctx.features if f in c.columns]
    n_params = max(_n_parameters(c, present), 1)
    minority = min(events, nonevents)
    return CheckResult("outcome_events", "ok", {
        "n_events": events, "n_nonevents": nonevents, "minority_class_n": minority,
        "n_parameters": n_params, "events_per_parameter": round(minority / n_params, 2),
    })


def check_leakage(ctx: Context) -> CheckResult:
    spec, c = ctx.spec, ctx.cohort
    if spec.task_type not in {"binary_classification", "survival"} or not ctx.features:
        return CheckResult("leakage", "skipped")
    if c is None or spec.outcome_column not in c.columns:
        return CheckResult("leakage", "not_evaluable", note="Outcome column unavailable.")
    declared = [f for f in ctx.features
                if ctx.coldefs.get(f, {}).get("timing") in {"post_index", "outcome"}]
    y = _binary_outcome(ctx, c)
    thr = ctx.params.get("leakage_auc_threshold", 0.95)
    aucs = {}
    for f in ctx.features:
        if f in c.columns:
            a = _auc(c[f], y)
            if a is not None:
                aucs[f] = a
    leaky = sorted([f for f, a in aucs.items() if a >= thr], key=lambda f: -aucs[f])
    top = max(aucs, key=aucs.get) if aucs else None
    return CheckResult("leakage", "ok", {
        "n_declared_post_index_features": len(declared),
        "declared_post_index_features": [safe_ident(f) for f in declared],
        "n_empirically_leaky_features": len(leaky),
        "empirically_leaky_features": [safe_ident(f) for f in leaky],
        "max_single_feature_auc": round(aucs[top], 3) if top else None,
        "dictionary_available": bool(ctx.dictionary),
    })


def check_temporal(ctx: Context) -> CheckResult:
    spec, c = ctx.spec, ctx.cohort
    if spec.time_horizon_months is None:
        return CheckResult("temporal", "skipped")
    if c is None or not spec.time_column or spec.time_column not in c.columns:
        return CheckResult("temporal", "not_evaluable", note="No follow-up time column for the stated horizon.")
    t = c[spec.time_column]
    observed = t >= spec.time_horizon_months
    if spec.outcome_column in c.columns:
        y = _binary_outcome(ctx, c).fillna(False).astype(bool)
        observed |= y & (t < spec.time_horizon_months)
    return CheckResult("temporal", "ok", {
        "horizon_months": spec.time_horizon_months,
        "horizon_coverage": round(float(observed.mean()), 3) if len(c) else 0.0,
        "median_follow_up_months": round(float(t.median()), 1) if len(c) else None,
    })


def check_subgroups(ctx: Context) -> CheckResult:
    spec, c = ctx.spec, ctx.cohort
    if not spec.subgroup_columns:
        return CheckResult("subgroups", "skipped")
    if c is None:
        return CheckResult("subgroups", "not_evaluable", note="Cohort undefined.")
    missing = [s for s in spec.subgroup_columns if s not in c.columns]
    min_n = ctx.params.get("min_subgroup_n", 50)
    small, smallest = [], None
    for s in spec.subgroup_columns:
        if s in missing:
            continue
        counts = c[s].value_counts(dropna=True)
        for cat, n in counts.items():
            if n < min_n:
                small.append(f"{safe_ident(s)}={safe_ident(cat)} (n={int(n)})")
            if smallest is None or n < smallest:
                smallest = int(n)
    return CheckResult("subgroups", "ok", {
        "n_missing_subgroup_columns": len(missing),
        "missing_subgroup_columns": [safe_ident(s) for s in missing],
        "n_small_subgroups": len(small), "small_subgroups": small[:10],
        "smallest_subgroup_n": smallest,
    })


def check_phi(ctx: Context) -> CheckResult:
    df = ctx.df
    hits: dict[str, str] = {}
    for col in df.columns:
        if PHI_NAME_HINTS.search(str(col)):
            hits[col] = "column_name"
            continue
        s = df[col].dropna()
        if s.empty or pd.api.types.is_numeric_dtype(s) and not str(col).lower().startswith("zip"):
            continue
        sample = s.astype(str).head(200)
        for kind, pat in PHI_VALUE_PATTERNS.items():
            if kind == "zip5" and not re.search(r"zip|postal", str(col), re.I):
                continue
            if sample.str.match(pat).mean() > 0.5:
                hits[col] = kind
                break
    why = {"column_name": "flagged by its name", "ssn": "values look like SSNs",
           "phone": "values look like phone numbers", "email": "values look like email addresses",
           "full_date": "values look like full dates", "zip5": "values look like ZIP codes"}
    return CheckResult("phi", "ok", {
        "n_phi_columns": len(hits),
        "phi_columns": [f"{safe_ident(c)} ({why.get(k, k)})" for c, k in hits.items()],
    })


def check_injection(ctx: Context) -> CheckResult:
    df = ctx.df
    locations = []
    for col in df.columns:
        if looks_like_injection(str(col)):
            locations.append(f"column_name:{safe_ident(col)}")
        if not pd.api.types.is_numeric_dtype(df[col]):  # object or pandas string dtype
            s = df[col].dropna().astype(str)
            flagged = s[s.map(looks_like_injection)]
            locations += [f"{safe_ident(col)}[row {i}]" for i in flagged.index[:5]]
    for col, meta in ctx.coldefs.items():
        if looks_like_injection(str(meta.get("description", ""))):
            locations.append(f"dictionary:{safe_ident(col)}")
    meta = (ctx.dictionary or {}).get("dataset", {}) or {}
    if any(looks_like_injection(str(v)) for v in meta.values()):
        locations.append("dictionary:dataset_metadata")
    # Note: only locations are reported. Flagged text is never echoed downstream.
    return CheckResult("injection", "ok", {
        "n_injection_hits": len(locations), "injection_locations": locations[:10],
    })


ALL_CHECKS = [
    check_metadata, check_scope, check_spec_quality, check_columns, check_cohort,
    check_completeness, check_outcome_events, check_leakage, check_temporal,
    check_subgroups, check_phi, check_injection,
]


def run_checks(df, dictionary, spec, params) -> list[CheckResult]:
    ctx = Context(df=df, dictionary=dictionary, spec=spec, params=params)
    results = []
    for fn in ALL_CHECKS:
        try:
            results.append(fn(ctx))
        except Exception as e:  # a crashing check must never silently pass
            name = fn.__name__.removeprefix("check_")
            results.append(CheckResult(name, "not_evaluable", note=f"Check error: {type(e).__name__}"))
    return results
