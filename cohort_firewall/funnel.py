"""Which samples can answer the question: who is left after each step, and why the rest dropped out.

Steps follow the question card: the group conditions in order, then outcome recorded, follow-up
recorded, all predictors recorded, and subgroup attributes recorded. The result is the complete-case
set that can answer the question exactly as asked, plus one row per input record saying whether it
was kept and, if not, at which step it dropped out.
"""
from __future__ import annotations

import csv
import io

import pandas as pd

from .sanitize import safe_ident
from .spec import QuestionSpec

OPS_TEXT = {"==": "is", "!=": "is not", "in": "is one of", "not_in": "is not one of",
            ">": "above", ">=": "at least", "<": "below", "<=": "at most"}


def _cond(df: pd.DataFrame, f) -> pd.Series:
    s = df[f.column]
    v = f.value
    return {"==": lambda: s == v, "!=": lambda: s != v,
            "in": lambda: s.isin(v if isinstance(v, list) else [v]),
            "not_in": lambda: ~s.isin(v if isinstance(v, list) else [v]),
            ">": lambda: s > v, ">=": lambda: s >= v, "<": lambda: s < v, "<=": lambda: s <= v}[f.op]().fillna(False)


def build_funnel(df: pd.DataFrame, dictionary: dict | None, spec: QuestionSpec) -> dict:
    cols = (dictionary or {}).get("columns", {}) or {}
    id_col = next((c for c, m in cols.items() if m.get("role") == "id" and c in df.columns), df.columns[0])
    pid_col = next((c for c, m in cols.items() if m.get("role") == "patient_id" and c in df.columns), None)
    keep = pd.Series(True, index=df.index)
    dropped_at = pd.Series("", index=df.index, dtype=object)
    steps = [{"step": "All records in the dataset", "n": int(len(df)), "dropped": 0}]

    def apply(label: str, mask: pd.Series):
        nonlocal keep
        newly = keep & ~mask
        dropped_at[newly] = label
        keep = keep & mask
        steps.append({"step": label, "n": int(keep.sum()), "dropped": int(newly.sum())})

    for f in spec.population_filters:
        if f.column in df.columns:
            val = ", ".join(map(str, f.value)) if isinstance(f.value, list) else f.value
            apply(f"{safe_ident(f.column)} {OPS_TEXT.get(f.op, f.op)} {safe_ident(val, 60)}", _cond(df, f))
    if spec.task_type != "descriptive" and spec.outcome_column in df.columns:
        apply(f"Outcome recorded ({safe_ident(spec.outcome_column)})", df[spec.outcome_column].notna())
    if spec.task_type != "descriptive" and spec.time_column and spec.time_column in df.columns:
        apply(f"Follow-up time recorded ({safe_ident(spec.time_column)})", df[spec.time_column].notna())
    feats = [c for c in spec.feature_columns if c in df.columns and c != "*"]
    if feats:
        apply(f"All {len(feats)} predictor(s) recorded", df[feats].notna().all(axis=1))
    subs = [c for c in spec.subgroup_columns if c in df.columns]
    if subs:
        apply("Subgroup attribute(s) recorded", df[subs].notna().all(axis=1))

    kept = df[keep]
    n_pat = int(kept[pid_col].nunique()) if pid_col else None
    not_in_data = [safe_ident(c) for c in spec.feature_columns + spec.subgroup_columns
                   if c not in df.columns and c != "*"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([id_col] + ([pid_col] if pid_col else []) + ["can_answer_question", "dropped_at_step"])
    for i, row in df.iterrows():
        w.writerow([row[id_col]] + ([row[pid_col]] if pid_col else []) +
                   ["yes" if keep[i] else "no", dropped_at[i]])
    return {
        "steps": steps, "n_final": int(keep.sum()), "n_patients_final": n_pat,
        "id_column": id_col, "patient_column": pid_col,
        "repeated_patients": (int(keep.sum()) - n_pat) if n_pat is not None else None,
        "not_in_data": not_in_data,
        "note": ("Complete cases: records with every field the question needs. The checks below judge the "
                 "larger group too, because imputation or other methods could keep more records."),
        "samples_csv": buf.getvalue(),
    }
