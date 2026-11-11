"""Print a SUMMARY of the event's TCGA-BRCA files: shapes, column names, value categories, counts.

It prints no patient-level rows, so its output is safe to share. Run it from the cohort-firewall repo
root, pointing at the cloned challenge repo:

  python scripts/profile_tcga.py ~/oncosys-hackathon-challenge > /tmp/tcga_profile.txt

It reads data/tcga-brca/raw/ (after fetch.py) and, if present, releases/practice-B/ file shapes only.
It never opens CHANGES.json.
"""
import csv
import hashlib
import sys
from pathlib import Path

import pandas as pd

repo = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("~/oncosys-hackathon-challenge").expanduser()
pack = repo / "data" / "tcga-brca"
raw = pack / "raw"
if not raw.exists():
    sys.exit(f"{raw} not found. Run: python data/tcga-brca/fetch.py  (from the challenge repo root)")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


print("=== checksums vs sources.csv ===")
for row in csv.DictReader(open(pack / "sources.csv")):
    p = raw / row["file"]
    print(f"{row['file']:28s} {'missing' if not p.exists() else ('ok' if sha(p) == row['sha256'] else 'MISMATCH')}")

clin = pd.read_csv(raw / "clinical.tsv", sep="\t", low_memory=False)
print(f"\n=== clinical.tsv: {clin.shape[0]} rows x {clin.shape[1]} columns ===")
print("ALL COLUMNS:", ", ".join(clin.columns))
key = ["sampleID", "sample_type", "breast_carcinoma_estrogen_receptor_status",
       "breast_carcinoma_progesterone_receptor_status", "lab_proc_her2_neu_immunohistochemistry_receptor_status",
       "PAM50Call_RNAseq", "pathologic_stage", "AJCC_Stage_nature2012", "pathologic_T", "pathologic_N",
       "pathologic_M", "race", "ethnicity", "gender", "vital_status", "menopause_status", "histological_type"]
for c in key:
    if c not in clin.columns:
        print(f"\n-- {c}: NOT FOUND")
        continue
    vc = clin[c].astype(str).value_counts(dropna=False)
    print(f"\n-- {c}: {clin[c].nunique(dropna=True)} distinct; top values: " +
          "; ".join(f"{k!r}={v}" for k, v in vc.head(10).items()) if c != "sampleID" else
          f"\n-- sampleID: {clin[c].nunique()} unique of {len(clin)}; example format length {clin[c].astype(str).str.len().mode().iloc[0]}")
for c in ["age_at_initial_pathologic_diagnosis", "days_to_death", "days_to_last_followup",
          "days_to_initial_pathologic_diagnosis"]:
    if c in clin.columns:
        s = pd.to_numeric(clin[c], errors="coerce")
        print(f"\n-- {c}: numeric {s.notna().sum()}, non-numeric strings {(s.isna() & clin[c].notna()).sum()} "
              f"(e.g. {clin.loc[s.isna() & clin[c].notna(), c].astype(str).value_counts().head(3).to_dict()}); "
              f"quantiles {s.quantile([0, .25, .5, .75, 1]).round(1).tolist()}")

surv = pd.read_csv(raw / "survival.tsv", sep="\t")
print(f"\n=== survival.tsv: {surv.shape} ===\ncolumns: {list(surv.columns)}")
print("non-null per column:", surv.notna().sum().to_dict())

for f in ["protein_rppa.tsv.gz", "mutation_gene_level.tsv.gz", "copy_number_gistic.tsv.gz", "rna_hiseq.tsv.gz"]:
    p = raw / f
    if not p.exists():
        print(f"\n=== {f}: not downloaded ===")
        continue
    m = pd.read_csv(p, sep="\t", index_col=0, nrows=5 if f.startswith("rna") else None)
    cols = list(m.columns)
    types = pd.Series([str(c)[13:15] for c in cols]).value_counts().to_dict()
    print(f"\n=== {f}: index name {m.index.name!r}, {'first 5 ' if f.startswith('rna') else ''}rows {m.shape[0]}, "
          f"sample columns {len(cols)} (unique {len(set(cols))}); sample-type codes {types}")
    print(f"first index entries: {list(m.index[:8])}")
    if f.startswith("protein"):
        print("ERALPHA present:", "ERALPHA" in m.index, "| missing share:", round(float(m.isna().mean().mean()), 3))

man = pd.read_csv(pack / "sample_manifest.csv")
print(f"\n=== sample_manifest.csv: {man.shape} ===\nsample_type: {man.sample_type.value_counts().to_dict()}")
print("patients with >1 sample:", int((man.groupby("patient_id").size() > 1).sum()))
sl = pd.read_csv(pack / "slide_manifest.csv")
print(f"\n=== slide_manifest.csv: {sl.shape} ===\ncolumns: {list(sl.columns)}")

rel = pack / "releases" / "practice-B"
if rel.exists():
    print("\n=== practice-B (file list and shapes only; CHANGES.json NOT read) ===")
    for p in sorted(rel.iterdir()):
        if p.name == "CHANGES.json":
            print("CHANGES.json present (not opened)")
            continue
        print(p.name, p.stat().st_size, "bytes")
