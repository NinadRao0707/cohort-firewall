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

# output column -> regex on observation DESCRIPTION.
# Breast patterns are anchored to the exact descriptions seen in our Synthea output
# (Nov 2026 inspect). Anchoring matters: "progesterone receptor" alone would also match
# the combined "Estrogen+Progesterone receptor" test.
FEATURE_KEYWORDS = {
    "breast": {
        "stage_group": r"^stage group\.clinical cancer",
        "t_class": r"^primary tumor\.clinical \[class\] cancer",
        "n_class": r"^regional lymph nodes\.clinical \[class\] cancer",
        "m_class": r"^distant metastases\.clinical \[class\] cancer",
        "er_status": r"^estrogen receptor ag \[presence\] in breast cancer specimen",
        "pr_status": r"^progesterone receptor ag \[presence\] in breast cancer specimen",
        "her2_ihc": r"^her2 \[presence\] in breast cancer specimen by immune stain",
        "her2_fish": r"^erbb2 gene duplication \[presence\] in breast cancer specimen by fish",
        "tumor_size": r"^size\.maximum dimension in tumor",
        "nodes_macromet": r"^lymph nodes with macrometastases \[#\]",
        "nodes_micromet": r"^lymph nodes with micrometastases \[#\]",
    },
    "lung": {},
    "colorectal": {"cea": r"carcinoembryonic"},
}
NUMERIC_FEATURES = {"tumor_size", "nodes_macromet", "nodes_micromet"}

# Candidate outcomes to examine before choosing one. Only post-index records can be outcomes.
OUTCOME_CANDIDATES = {
    "breast": {
        "treatment_response": r"^response to cancer treatment",
        "treatment_status": r"^treatment status cancer",
    },
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


ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}


def _norm_stage(v):
    m = re.search(r"stage\s*(IV|III|II|I|[1-4])", str(v), re.IGNORECASE)
    if not m:
        return None
    tok = m.group(1).upper()
    return ROMAN.get(tok, tok)


def _norm_tnm(v):
    m = re.search(r"\bc([TNM][0-4X])", str(v))
    return m.group(1) if m else None


def _norm_receptor(v):
    t = str(v).lower()
    return "positive" if "positive" in t else "negative" if "negative" in t else None


def _norm_fish(v):
    t = str(v).lower()
    if "greater than" in t:
        return "amplified"
    if "less than" in t:
        return "not_amplified"
    return "equivocal" if t.strip() and t != "nan" else None


NORMALIZERS = {
    "stage_group": _norm_stage, "t_class": _norm_tnm, "n_class": _norm_tnm, "m_class": _norm_tnm,
    "er_status": _norm_receptor, "pr_status": _norm_receptor, "her2_ihc": _norm_receptor,
    "her2_fish": _norm_fish,
}
PROGRESSION_PATTERN = r"^response to cancer treatment"
PROGRESSION_VALUE = r"worsening"
PROGRESSION_DAYS = 730


def inspect_values(synthea_dir: Path, cancer: str, window_days: int):
    """Report, for every mapped feature and outcome candidate: coverage, timing, top values."""
    patients = _read(synthea_dir, "patients")
    conditions = _read(synthea_dir, "conditions")
    observations = _read(synthea_dir, "observations")
    desc = conditions["DESCRIPTION"].astype(str)
    match = desc.str.contains(CANCER_PATTERNS[cancer], case=False, regex=True) & \
        desc.str.contains(CANCER_GUARD, case=False, regex=True)
    cond = conditions[match].copy()
    cond["START"] = _dates(cond["START"])
    index = cond.groupby("PATIENT")["START"].min().rename("idx")
    n = len(index)
    print(f"{n} patients; baseline window +/-{window_days} days of first diagnosis\n")

    obs = observations[observations["PATIENT"].isin(index.index)].copy()
    obs["DATE"] = _dates(obs["DATE"])
    obs = obs.join(index, on="PATIENT")
    obs["days"] = (obs["DATE"] - obs["idx"]).dt.days
    d = obs["DESCRIPTION"].astype(str)

    def report(name, pat):
        o = obs[d.str.contains(pat, case=False, regex=True)]
        if o.empty:
            print(f"--- {name}: NO MATCHES for pattern {pat!r}\n")
            return
        any_p = o["PATIENT"].nunique()
        in_win = o[o["days"].abs() <= window_days]["PATIENT"].nunique()
        after = o[o["days"] > window_days]["PATIENT"].nunique()
        q = o["days"].quantile([0, 0.25, 0.5, 0.75, 1]).round(0).astype(int).tolist()
        print(f"--- {name}")
        print(f"patients with any record: {any_p}/{n} | within window: {in_win} | "
              f"only/also later than window: {after}")
        print(f"days from diagnosis (min, q1, median, q3, max): {q}")
        print("top values:", o["VALUE"].astype(str).value_counts().head(8).to_dict(), "\n")

    print("=== FEATURES ===")
    for name, pat in FEATURE_KEYWORDS.get(cancer, {}).items():
        report(name, pat)
    print("=== OUTCOME CANDIDATES ===")
    for name, pat in OUTCOME_CANDIDATES.get(cancer, {}).items():
        report(name, pat)

    p = patients[patients["ID"].isin(index.index)].set_index("ID")
    death = _dates(p.get("DEATHDATE"))
    dd = (death - index.reindex(p.index)).dt.days.dropna()
    print("=== DEATH ===")
    print(f"deaths: {len(dd)}/{n}; days from diagnosis to death (min, q1, median, q3, max): "
          f"{dd.quantile([0, .25, .5, .75, 1]).round(0).astype(int).tolist() if len(dd) else []}")
    last = obs.groupby("PATIENT")["DATE"].max()
    end = death.where(death.notna(), last.reindex(p.index))
    fu = ((end - index.reindex(p.index)).dt.days / 30.44).dropna()
    print(f"follow-up months (min, q1, median, q3, max): {fu.quantile([0, .25, .5, .75, 1]).round(1).tolist()}")
    print(f"share followed >= 24 months: {(fu >= 24).mean():.0%}; >= 60 months: {(fu >= 60).mean():.0%}")
    print(f"diagnosis years: {index.dt.year.value_counts().sort_index().to_dict()}")


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
        units = {}
        for col, pat in FEATURE_KEYWORDS.get(cancer, {}).items():
            hit = obs[obs["DESCRIPTION"].astype(str).str.contains(pat, case=False, regex=True)].copy()
            if col in NORMALIZERS:
                hit["VALUE"] = hit["VALUE"].map(NORMALIZERS[col])
            elif col in NUMERIC_FEATURES:
                hit["VALUE"] = pd.to_numeric(hit["VALUE"], errors="coerce")
                if "UNITS" in hit.columns and hit["UNITS"].notna().any():
                    units[col] = str(hit["UNITS"].mode().iloc[0])
            hit = hit.dropna(subset=["VALUE"]).sort_values("DATE").groupby("PATIENT")["VALUE"].first()
            out[col] = hit.reindex(out.index)

    # Outcome proxy: any "Worsening" treatment response within PROGRESSION_DAYS after diagnosis.
    # 0 only if the patient was followed past PROGRESSION_DAYS without one; unknown otherwise.
    if observations is not None:
        allobs = observations[observations["PATIENT"].isin(ids)].copy()
        allobs["DATE"] = _dates(allobs["DATE"])
        allobs = allobs.join(idx.rename("idx"), on="PATIENT")
        days = (allobs["DATE"] - allobs["idx"]).dt.days
        worse = allobs[allobs["DESCRIPTION"].astype(str).str.contains(PROGRESSION_PATTERN, case=False, regex=True)
                       & allobs["VALUE"].astype(str).str.contains(PROGRESSION_VALUE, case=False, regex=True)
                       & (days > 0) & (days <= PROGRESSION_DAYS)]
        prog = pd.Series(0.0, index=out.index)
        prog[out.index.isin(worse["PATIENT"].unique())] = 1.0
        followed = out["follow_up_months"] >= PROGRESSION_DAYS / 30.44
        out[f"progression_{PROGRESSION_DAYS // 365}yr"] = prog.where((prog == 1) | followed)
    died_by = out["death_event"].eq(1) & (out["follow_up_months"] <= 24)
    out["death_2yr"] = died_by.astype(float).where(died_by | (out["follow_up_months"] >= 24))

    out = out.reset_index(drop=True)
    coldefs = {c: {"type": "numeric" if pd.api.types.is_numeric_dtype(out[c]) else "categorical",
                   "role": "feature", "timing": "baseline", "description": c} for c in out.columns}
    coldefs["patient_id"].update(role="id", type="id", description="New pseudonymous id")
    for c in ("sex", "race", "ethnicity", "age_at_diagnosis"):
        coldefs[c]["role"] = "demographic"
    coldefs["follow_up_months"].update(role="time", timing="outcome")
    coldefs["death_event"].update(role="outcome", timing="outcome", type="binary",
                                  description="Death recorded during follow-up")
    for c in [c for c in out.columns if c.startswith("progression_")]:
        coldefs[c].update(role="outcome", timing="outcome", type="binary",
                          description=f"Synthea proxy for progression: any 'Worsening' treatment response "
                                      f"within {PROGRESSION_DAYS} days of diagnosis (blank if follow-up too short)")
    coldefs["death_2yr"].update(role="outcome", timing="outcome", type="binary",
                                description="Death within 24 months of diagnosis (blank if follow-up too short)")
    for c, u in (units if observations is not None else {}).items():
        coldefs[c]["description"] = f"{c} (unit as reported by Synthea: {u})"
    for c in ("stage_group", "t_class", "n_class", "m_class"):
        if c in coldefs:
            coldefs[c]["type"] = "categorical"
    dictionary = {"dataset": {
        "name": f"synthea_{cancer}_cohort",
        "source": "Synthea synthetic patient generator (MITRE), flattened by data/flatten_synthea.py",
        "provenance": f"Flattened from {synthea_dir.name}; identifiers removed; baseline window "
                      f"+/-{BASELINE_WINDOW_DAYS} days of first {cancer} cancer condition.",
        "license": "Apache-2.0",  # confirm the license that applies to your Synthea output
        "patient_derived": False,
        "identifiable": False,
        "access": "open",
    }, "columns": coldefs}
    return out, dictionary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthea-dir", required=True, type=Path)
    ap.add_argument("--cancer", choices=sorted(CANCER_PATTERNS), default="breast")
    ap.add_argument("--out", type=Path, default=Path("data/synthea"))
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--inspect-values", action="store_true",
                    help="coverage, timing and top values for each mapped field and outcome candidate")
    ap.add_argument("--window-days", type=int, default=BASELINE_WINDOW_DAYS)
    a = ap.parse_args()
    BASELINE_WINDOW_DAYS = a.window_days
    if a.inspect_values:
        inspect_values(a.synthea_dir, a.cancer, a.window_days)
        raise SystemExit(0)
    df, d = build(a.synthea_dir, a.cancer, a.inspect)
    if df is not None:
        a.out.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out / f"{a.cancer}_cohort.csv", index=False)
        (a.out / f"{a.cancer}_cohort.dictionary.json").write_text(json.dumps(d, indent=2, default=str))
        print(f"wrote {len(df)} patients to {a.out}\n")
        era = (df["diagnosis_year"] >= 2012).map({True: "2012+", False: "before 2012"})
        feats = [c for c in FEATURE_KEYWORDS.get(a.cancer, {}) if c in df.columns]
        print("Share MISSING by diagnosis era:")
        print(df[feats].isna().groupby(era).mean().round(2).T.to_string(), "\n")
        outs = [c for c in df.columns if c.startswith("progression_") or c in ("death_2yr", "death_event")]
        print("Outcome counts for patients diagnosed 2012+ (1 = event, 0 = no event, NaN = unknown):")
        recent = df[df["diagnosis_year"] >= 2012]
        for c in outs:
            print(f"  {c}: {recent[c].value_counts(dropna=False).to_dict()}")
        print("\nRace counts (2012+):", recent["race"].value_counts().to_dict())
        print("Ethnicity counts (2012+):", recent["ethnicity"].value_counts().to_dict())
        for c in ("stage_group", "er_status", "her2_ihc"):
            if c in df.columns:
                print(f"{c} values (2012+):", recent[c].value_counts(dropna=False).to_dict())
