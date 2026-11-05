"""Flatten a Synthea CSV export into one patient-level oncology cohort table.

Synthea writes separate tables (patients.csv, conditions.csv, observations.csv, ...).
This script builds one row per patient with a matching cancer condition:
  index date       = first matching condition START
  diagnosis_year   = year only (full dates are identifiers under HIPAA Safe Harbor)
  age_at_diagnosis = whole years between BIRTHDATE and index date
  follow_up_months = index date -> DEATHDATE, else -> last recorded observation/encounter date
  death_event      = 1 if DEATHDATE is present
  baseline features from observations within +/- BASELINE_WINDOW_DAYS of the index date

Direct identifiers (names, SSN, driver's license, passport, address, ZIP, lat/lon, full dates)
are never written to the output. The dictionary JSON is written alongside.

How Synthea represents stage, receptor status and recurrence varies by module and version,
so feature mapping is keyword-based and meant to be filled in after a quick inspection:

  python data/flatten_synthea.py --synthea-dir output/csv --cancer breast --inspect
  python data/flatten_synthea.py --synthea-dir output/csv --cancer breast --out data/synthea

Column names are matched case-insensitively; verify them against your Synthea version.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

CANCER_PATTERNS = {  # matched against condition DESCRIPTION; edit after --inspect
    "breast": r"malignant neoplasm of breast|carcinoma of breast|breast cancer",
    "lung": r"lung|bronch",
    "colorectal": r"colon|rectum|rectal|colorectal",
}
CANCER_GUARD = r"malignant|carcinoma|cancer|neoplasm"

# output column -> regex on observation DESCRIPTION (fill in after --inspect)
FEATURE_KEYWORDS = {
    "breast": {
        "er_status": r"estrogen receptor",
        "pr_status": r"progesterone receptor",
        "her2_status": r"\bher2\b|erbb2",
        "tumor_size_mm": r"tumor size|size\.?\s*tumor|greatest dimension",
    },
    "lung": {},
    "colorectal": {"cea": r"carcinoembryonic"},
}
BASELINE_WINDOW_DAYS = 90


def _read(d: Path, name: str, required=True) -> pd.DataFrame | None:
    p = d / f"{name}.csv"
    if not p.exists():
        if required:
            raise SystemExit(f"missing {p}")
        return None
    df = pd.read_csv(p, low_memory=False)
    df.columns = [c.upper() for c in df.columns]
    return df


def _dates(s):
    return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)


def build(synthea_dir: Path, cancer: str, inspect: bool = False):
    patients = _read(synthea_dir, "patients")
    conditions = _read(synthea_dir, "conditions")
    observations = _read(synthea_dir, "observations", required=False)
    encounters = _read(synthea_dir, "encounters", required=False)

    desc = conditions["DESCRIPTION"].astype(str)
    match = desc.str.contains(CANCER_PATTERNS[cancer], case=False, regex=True) & \
        desc.str.contains(CANCER_GUARD, case=False, regex=True)
    cond = conditions[match].copy()
    cond["START"] = _dates(cond["START"])
    index = cond.groupby("PATIENT")["START"].min().rename("index_date")
    ids = set(index.index)

    if inspect:
        print(f"{len(ids)} patients matched '{cancer}'. Matching condition descriptions:")
        print(cond["DESCRIPTION"].value_counts().head(20).to_string())
        if observations is not None:
            obs = observations[observations["PATIENT"].isin(ids)]
            print("\nMost common observation descriptions for these patients:")
            print(obs["DESCRIPTION"].value_counts().head(60).to_string())
        other = conditions[conditions["PATIENT"].isin(ids) & ~match]
        print("\nOther conditions for these patients (look for stage / metastasis / recurrence):")
        print(other["DESCRIPTION"].value_counts().head(40).to_string())
        return None, None

    p = patients[patients["ID"].isin(ids)].set_index("ID")
    birth, death = _dates(p["BIRTHDATE"]), _dates(p.get("DEATHDATE"))
    idx = index.reindex(p.index)

    last_seen = pd.Series(pd.NaT, index=p.index, dtype="datetime64[ns]")
    for tbl, col in ((observations, "DATE"), (encounters, "START")):
        if tbl is not None and col in tbl.columns:
            t = tbl[tbl["PATIENT"].isin(ids)].copy()
            t[col] = _dates(t[col])
            last_seen = pd.concat([last_seen, t.groupby("PATIENT")[col].max()], axis=1).max(axis=1)
    end = death.where(death.notna(), last_seen)

    out = pd.DataFrame(index=p.index)
    out["patient_id"] = [f"S{i:06d}" for i in range(len(p))]  # new pseudonym, not the Synthea UUID
    out["cancer_type"] = cancer
    out["diagnosis_year"] = idx.dt.year
    out["age_at_diagnosis"] = ((idx - birth).dt.days // 365.25).astype("Int64")
    out["sex"] = p.get("GENDER")
    out["race"] = p.get("RACE")
    out["ethnicity"] = p.get("ETHNICITY")
    out["follow_up_months"] = ((end - idx).dt.days / 30.44).round(1)
    out["death_event"] = death.notna().astype(int)

    if observations is not None:
        obs = observations[observations["PATIENT"].isin(ids)].copy()
        obs["DATE"] = _dates(obs["DATE"])
        obs = obs.join(idx.rename("idx"), on="PATIENT")
        obs = obs[(obs["DATE"] - obs["idx"]).abs().dt.days <= BASELINE_WINDOW_DAYS]
        for col, pat in FEATURE_KEYWORDS.get(cancer, {}).items():
            hit = obs[obs["DESCRIPTION"].astype(str).str.contains(pat, case=False, regex=True)]
            hit = hit.sort_values("DATE").groupby("PATIENT")["VALUE"].first()
            out[col] = hit.reindex(out.index)

    out = out.reset_index(drop=True)
    coldefs = {c: {"type": "numeric" if pd.api.types.is_numeric_dtype(out[c]) else "categorical",
                   "role": "feature", "timing": "baseline", "description": c} for c in out.columns}
    coldefs["patient_id"].update(role="id", type="id", description="New pseudonymous id")
    for c in ("sex", "race", "ethnicity", "age_at_diagnosis"):
        coldefs[c]["role"] = "demographic"
    coldefs["follow_up_months"].update(role="time", timing="outcome")
    coldefs["death_event"].update(role="outcome", timing="outcome", type="binary")
    dictionary = {"dataset": {
        "name": f"synthea_{cancer}_cohort",
        "source": "Synthea synthetic patient generator (MITRE), flattened by data/flatten_synthea.py",
        "provenance": f"Flattened from {synthea_dir.name}; identifiers removed; baseline window "
                      f"+/-{BASELINE_WINDOW_DAYS} days of first {cancer} cancer condition.",
        "license": "Apache-2.0",  # confirm the license that applies to your Synthea output
        "contains_real_patient_data": False,
    }, "columns": coldefs}
    return out, dictionary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthea-dir", required=True, type=Path)
    ap.add_argument("--cancer", choices=sorted(CANCER_PATTERNS), default="breast")
    ap.add_argument("--out", type=Path, default=Path("data/synthea"))
    ap.add_argument("--inspect", action="store_true")
    a = ap.parse_args()
    df, d = build(a.synthea_dir, a.cancer, a.inspect)
    if df is not None:
        a.out.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out / f"{a.cancer}_cohort.csv", index=False)
        (a.out / f"{a.cancer}_cohort.dictionary.json").write_text(json.dumps(d, indent=2, default=str))
        print(f"wrote {len(df)} patients to {a.out}")
