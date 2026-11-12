"""Datasets the server can check without an upload, and a column summary for the question-card form."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("tcga_brca_raw", "TCGA-BRCA, frozen event release (judged data)", ROOT / "data" / "tcga" / "tcga_brca_raw"),
    ("demo_breast_cohort", "Synthetic stand-in cohort (engine testing only)", ROOT / "data" / "demo" / "breast_cohort"),
]


def available() -> list[dict]:
    out = []
    for did, label, stem in SOURCES:
        csv, dct = stem.with_suffix(".csv"), stem.with_suffix(".dictionary.json")
        if csv.exists() and dct.exists():
            out.append({"id": did, "label": label, "csv": csv, "dictionary": dct})
    return out


def get(did: str) -> dict | None:
    return next((d for d in available() if d["id"] == did), None)


def describe(did: str) -> dict:
    d = get(did)
    if d is None:
        raise KeyError(did)
    df = pd.read_csv(d["csv"], low_memory=False)
    dictionary = json.loads(d["dictionary"].read_text())
    cols = []
    for name, meta in dictionary.get("columns", {}).items():
        if name not in df.columns:
            continue
        s = df[name]
        info = {"name": name, "type": meta.get("type"), "role": meta.get("role"),
                "timing": meta.get("timing"), "unit": meta.get("unit"),
                "description": meta.get("description", ""), "missing": round(float(s.isna().mean()), 3)}
        if meta.get("role") in {"id", "patient_id"}:
            pass
        elif pd.api.types.is_numeric_dtype(s) and s.nunique() > 12:
            info["min"], info["max"] = (float(s.min()), float(s.max())) if s.notna().any() else (None, None)
        else:
            vc = s.value_counts(dropna=True)
            info["values"] = [{"value": (v.item() if hasattr(v, "item") else v), "n": int(n)}
                              for v, n in vc.head(40).items()]
        cols.append(info)
    return {"id": did, "label": d["label"], "n_rows": int(len(df)),
            "dataset": dictionary.get("dataset", {}), "columns": cols}
