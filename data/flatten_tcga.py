"""Flatten the event's frozen TCGA-BRCA release into one readiness table + data dictionary.

One row per SAMPLE in clinical.tsv (all sample types kept, so the firewall can see patients with
several samples). Joins only on documented TCGA barcodes: clinical sampleID = survival sample =
manifest sample_id = protein column. Every source file is checked against sources.csv first; the
dictionary records which files were verified, and the firewall treats unverified files as
Insufficient Evidence (META-009).

Raw TCGA values are never committed: the output goes to data/tcga/ (git-ignored).

  python data/flatten_tcga.py --challenge-repo ~/oncosys-hackathon-challenge
  python data/flatten_tcga.py --challenge-repo ~/oncosys-hackathon-challenge --release releases/practice-B
"""
import argparse
import csv
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

CLINICAL = {  # output column -> clinical.tsv column
    "er_status": "breast_carcinoma_estrogen_receptor_status",
    "pr_status": "breast_carcinoma_progesterone_receptor_status",
    "her2_ihc_status": "lab_proc_her2_neu_immunohistochemistry_receptor_status",
    "pam50_subtype": "PAM50Call_RNAseq",
    "pathologic_stage": "pathologic_stage",
    "t_stage": "pathologic_T", "n_stage": "pathologic_N", "m_stage": "pathologic_M",
    "age_at_diagnosis": "age_at_initial_pathologic_diagnosis",
    "gender": "gender", "menopause_status": "menopause_status",
    "histological_type": "histological_type",
    "days_to_last_followup": "days_to_last_followup",
    "vital_status": "vital_status",
    # Second sources for the same facts (TCGA 2012 Nature paper calls), used for consistency checks
    "er_status_nature2012": "ER_Status_nature2012",
    "pr_status_nature2012": "PR_Status_nature2012",
    "pam50_nature2012": "PAM50_mRNA_nature2012",
}
RANGES = {"age_at_diagnosis": [18, 100], "days_to_last_followup": [0, 12000], "os_days": [0, 12000],
          "pfi_days": [0, 12000], "dss_days": [0, 12000], "dfi_days": [0, 12000]}
CONSISTENCY = [
    {"a": "er_status", "b": "er_status_nature2012", "label": "ER status: clinical file vs 2012 paper"},
    {"a": "pr_status", "b": "pr_status_nature2012", "label": "PR status: clinical file vs 2012 paper"},
    {"a": "pam50_subtype", "b": "pam50_nature2012", "normalize": "pam50",
     "label": "PAM50 subtype: RNA-seq call vs 2012 microarray call"},
    {"a": "vital_status", "b": "os_event", "map": {"DECEASED": "1.0", "LIVING": "0.0"},
     "label": "Vital status (clinical) vs overall-survival event (curated)"},
]
SURVIVAL = {"os_event": "OS", "os_days": "OS.time", "pfi_event": "PFI", "pfi_days": "PFI.time",
            "dss_event": "DSS", "dss_days": "DSS.time", "dfi_event": "DFI", "dfi_days": "DFI.time"}
LAYERS = ["has_survival", "has_mutation", "has_copy_number", "has_rna", "has_protein"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_sha256(p: Path) -> str:
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def stage_group(v):
    m = re.match(r"Stage (IV|III|II|I)", str(v))
    return m.group(1) if m else None          # "Stage X" (not assessable) and blanks -> missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenge-repo", type=Path, required=True)
    ap.add_argument("--release", default="raw", help="folder under data/tcga-brca/ (default raw)")
    ap.add_argument("--out", type=Path, default=Path("data/tcga"))
    a = ap.parse_args()
    pack = a.challenge_repo.expanduser() / "data" / "tcga-brca"
    rel = pack / a.release

    # 1. verify sources
    frozen = {r["file"]: r for r in csv.DictReader(open(pack / "sources.csv"))}
    content = {}
    hashes_file = pack / f"{rel.name}.content.sha256"
    if hashes_file.exists():
        for line in hashes_file.read_text().splitlines():
            if line.strip():
                h, f = line.split()
                content[f] = h
    used = ["clinical.tsv", "survival.tsv", "protein_rppa.tsv.gz"]
    source_files = []
    for f in used:
        p = rel / f
        if a.release == "raw":
            ok = p.exists() and sha256(p) == frozen[f]["sha256"]
            how = "file sha256 vs sources.csv"
        else:
            ok = p.exists() and content.get(f) == content_sha256(p)
            how = f"content sha256 vs {hashes_file.name}" if content else "no published hashes"
        source_files.append({"file": f, "release": rel.name, "verified": bool(ok), "method": how,
                             "license": frozen.get(f, {}).get("license", "")})
        print(f"{'verified ' if ok else 'UNVERIFIED'} {f} ({how})")

    # 2. build the table (documented barcode joins only)
    clin = pd.read_csv(rel / "clinical.tsv", sep="\t", dtype=str, keep_default_na=False)
    surv = pd.read_csv(rel / "survival.tsv", sep="\t", dtype=str, keep_default_na=False)
    man = pd.read_csv(pack / "sample_manifest.csv", dtype=str)
    prot = pd.read_csv(rel / "protein_rppa.tsv.gz", sep="\t", index_col=0)

    out = pd.DataFrame({"sample_id": clin["sampleID"], "patient_id": clin["sampleID"].str[:12],
                        "sample_type": clin["sample_type"]})
    for new, old in CLINICAL.items():
        out[new] = clin[old].replace({"": None}) if old in clin.columns else None
    out["stage_group"] = out["pathologic_stage"].map(stage_group)
    # "Post (prior bilateral ovariectomy OR ...)" -> "Post"; the full wording stays in the source file
    out["menopause_status"] = out["menopause_status"].map(lambda v: str(v).split(" (")[0] if v else None)
    out["t_stage"] = out["t_stage"].replace({"TX": None})
    out["m_stage"] = out["m_stage"].replace({"MX": None})
    for c in ("age_at_diagnosis", "days_to_last_followup"):
        out[c] = pd.to_numeric(out[c], errors="coerce")

    s = surv.set_index("sample")
    for new, old in SURVIVAL.items():
        out[new] = pd.to_numeric(out["sample_id"].map(s[old]) if old in s.columns else None, errors="coerce")
    # Derived research endpoint: progression-free interval event within 2 years (blank if unknown)
    pfi2 = (out["pfi_event"] == 1) & (out["pfi_days"] <= 730)
    out["pfi_2yr"] = pfi2.astype(float).where(pfi2 | (out["pfi_days"] >= 730))

    m = man.set_index("sample_id")
    for c in LAYERS + ["slides_for_sample"]:
        if c in m.columns:
            col = out["sample_id"].map(m[c])
            out[c] = col.map({"True": 1, "False": 0}) if c.startswith("has_") else pd.to_numeric(col, errors="coerce")
    out["er_alpha_rppa"] = out["sample_id"].map(prot.loc["ERALPHA"]) if "ERALPHA" in prot.index else None

    # 3. dictionary
    col = lambda t, r, timing, d, **kw: {"type": t, "role": r, "timing": timing, "description": d, **kw}
    cols = {
        "sample_id": col("id", "id", "baseline", "TCGA sample barcode (15 characters)"),
        "patient_id": col("id", "patient_id", "baseline", "TCGA patient barcode (first 12 characters)"),
        "sample_type": col("categorical", "feature", "baseline", "Primary Tumor, Solid Tissue Normal or Metastatic"),
        "er_status": col("categorical", "feature", "baseline", "Clinical ER status (IHC)"),
        "pr_status": col("categorical", "feature", "baseline", "Clinical PR status (IHC)"),
        "her2_ihc_status": col("categorical", "feature", "baseline", "Clinical HER2 status (IHC); includes Equivocal"),
        "pam50_subtype": col("categorical", "feature", "baseline", "PAM50 subtype from RNA-seq"),
        "pathologic_stage": col("categorical", "feature", "baseline", "Pathologic stage as recorded"),
        "stage_group": col("categorical", "feature", "baseline", "Stage group I-IV; Stage X (not assessable) is missing"),
        "t_stage": col("categorical", "feature", "baseline", "Pathologic T; TX is missing"),
        "n_stage": col("categorical", "feature", "baseline", "Pathologic N"),
        "m_stage": col("categorical", "feature", "baseline", "Pathologic M; MX is missing"),
        "age_at_diagnosis": col("numeric", "demographic", "baseline", "Age in years at initial diagnosis"),
        "gender": col("categorical", "demographic", "baseline", "Recorded gender"),
        "menopause_status": col("categorical", "demographic", "baseline", "Menopause status at diagnosis (Pre, Peri, Post, Indeterminate)"),
        "histological_type": col("categorical", "feature", "baseline", "Histological type"),
        "days_to_last_followup": col("numeric", "time", "outcome", "Days to last follow-up (clinical file)", unit="days"),
        "os_event": col("binary", "outcome", "outcome", "Overall survival event (curated, TCGA-CDR)"),
        "os_days": col("numeric", "time", "outcome", "Overall survival time", unit="days"),
        "pfi_event": col("binary", "outcome", "outcome", "Progression-free interval event (TCGA-CDR)"),
        "pfi_days": col("numeric", "time", "outcome", "Progression-free interval time", unit="days"),
        "dss_event": col("binary", "outcome", "outcome", "Disease-specific survival event"),
        "dss_days": col("numeric", "time", "outcome", "Disease-specific survival time", unit="days"),
        "dfi_event": col("binary", "outcome", "outcome", "Disease-free interval event"),
        "dfi_days": col("numeric", "time", "outcome", "Disease-free interval time", unit="days"),
        "pfi_2yr": col("binary", "outcome", "outcome", "PFI event within 730 days; blank if follow-up shorter and no event"),
        "er_alpha_rppa": col("numeric", "feature", "baseline", "ER-alpha protein level (RPPA); blank if not profiled"),
        "slides_for_sample": col("numeric", "availability", "baseline", "Slides in IDC matching this sample"),
        "vital_status": col("categorical", "outcome", "outcome", "Vital status in the clinical file (LIVING, DECEASED)"),
        "er_status_nature2012": col("categorical", "feature", "baseline", "ER status from the 2012 TCGA paper (second source)"),
        "pr_status_nature2012": col("categorical", "feature", "baseline", "PR status from the 2012 TCGA paper (second source)"),
        "pam50_nature2012": col("categorical", "feature", "baseline", "PAM50 call from the 2012 paper's microarray data (second source)"),
    }
    for c, r in RANGES.items():
        cols[c]["valid_range"] = r
    for c in LAYERS:
        cols[c] = col("binary", "availability", "baseline", f"Sample appears in the {c[4:]} file")
    dictionary = {"dataset": {
        "name": f"tcga_brca_{rel.name}",
        "source": "OncoSys hackathon frozen TCGA-BRCA release (UCSC Xena TCGA hub; survival from TCGA-CDR)",
        "provenance": f"Flattened by data/flatten_tcga.py from {rel.name}; joins on TCGA barcodes only.",
        "license": "event-approved",
        "license_note": "TCGA open access, redistribution terms being confirmed by organizers; not redistributed here.",
        "patient_derived": True, "identifiable": False, "access": "open",
        "source_files": source_files,
        "consistency_pairs": CONSISTENCY,
    }, "columns": cols}

    a.out.mkdir(parents=True, exist_ok=True)
    stem = f"tcga_brca_{rel.name}"
    out.to_csv(a.out / f"{stem}.csv", index=False)
    (a.out / f"{stem}.dictionary.json").write_text(json.dumps(dictionary, indent=2))
    prim = out[out.sample_type == "Primary Tumor"]
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cohort_firewall.checks import _norm
    print("\nAgreement between sources (primary tumors, both values present):")
    for pair in CONSISTENCY:
        xa = prim[pair["a"]].map(lambda v: _norm(v, pair.get("normalize"), pair.get("map")))
        xb = prim[pair["b"]].map(lambda v: _norm(v, pair.get("normalize"), None))
        both = xa.notna() & xb.notna()
        if both.sum():
            print(f"  {pair['label']}: {int((xa[both] != xb[both]).sum())} of {int(both.sum())} disagree "
                  f"({(xa[both] != xb[both]).mean():.0%}); values {sorted(set(xa[both]))[:6]} vs {sorted(set(xb[both]))[:6]}")
        else:
            print(f"  {pair['label']}: no records with both values")
    print(f"\nwrote {len(out)} samples ({out.patient_id.nunique()} patients) to {a.out}/{stem}.csv")
    print(f"primary tumors: {len(prim)}; with protein: {int(prim.has_protein.sum())}; "
          f"PFI 2yr events/known: {int(prim.pfi_2yr.sum())}/{int(prim.pfi_2yr.notna().sum())}; "
          f"OS events: {int(prim.os_event.sum())}; median OS days {prim.os_days.median():.0f}")


if __name__ == "__main__":
    main()
