"""Build small FAKE releases in the TCGA-BRCA file layout, with our own randomized changes.

Used to test the Control Tower without real data. Values are random; IDs only look like barcodes.
Also writes a stand-in challenge repo (sources.csv + our own A1/A2 implementation of the documented
reference analyses), so tests run without the real challenge repo.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

FILES = ["clinical.tsv", "survival.tsv", "protein_rppa.tsv.gz", "mutation_gene_level.tsv.gz",
         "copy_number_gistic.tsv.gz"]
STAND_IN_ANALYSES = '''"""Stand-in for the challenge repo's reference analyses (same documented behavior), for tests only."""
import pandas as pd

def primary(ids):
    return [i for i in ids if str(i)[13:15] == "01"]

def a1(clinical, protein):
    """Mean ER-alpha (RPPA) in ER-positive vs ER-negative primary tumors (clinical IHC status)."""
    er = clinical.set_index("sampleID")["breast_carcinoma_estrogen_receptor_status"]
    samples = [s for s in primary(protein.columns) if er.get(s) in ("Positive", "Negative")]
    vals = protein.loc["ERALPHA", samples]
    pos = vals[[s for s in samples if er[s] == "Positive"]]
    neg = vals[[s for s in samples if er[s] == "Negative"]]
    return {"analysis": "A1", "inputs": ["clinical.tsv", "protein_rppa.tsv.gz"], "n_samples": len(samples),
            "sample_ids": sorted(samples), "n_positive": int(pos.size), "n_negative": int(neg.size),
            "mean_positive": round(float(pos.mean()), 3), "mean_negative": round(float(neg.mean()), 3),
            "difference": round(float(pos.mean() - neg.mean()), 3)}

def a2(clinical):
    """Share of primary tumors in each PAM50 RNA-seq subtype (subtyped samples only)."""
    c = clinical[clinical.sampleID.str[13:15] == "01"].dropna(subset=["PAM50Call_RNAseq"])
    counts = c.PAM50Call_RNAseq.value_counts().sort_index()
    return {"analysis": "A2", "inputs": ["clinical.tsv"], "n_samples": int(counts.sum()),
            "sample_ids": sorted(c.sampleID), "counts": {k: int(v) for k, v in counts.items()},
            "percent": {k: round(100 * v / counts.sum(), 1) for k, v in counts.items()}}
'''


def _write(df: pd.DataFrame, path: Path, index: bool):
    text = df.to_csv(sep="\t", index=index)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", compresslevel=6) as f:
            f.write(text)
    else:
        path.write_text(text)


def _read(path: Path, matrix: bool) -> pd.DataFrame:
    kw = dict(sep="\t", dtype=str, keep_default_na=False)
    return pd.read_csv(path, index_col=0, **kw) if matrix else pd.read_csv(path, **kw)


def make_baseline(dest: Path, seed: int = 7, n_patients: int = 260) -> list[str]:
    rng = np.random.default_rng(seed)
    dest.mkdir(parents=True, exist_ok=True)
    pats = [f"TCGA-{rng.integers(10, 99)}-{i:04X}" for i in range(n_patients)]
    samples = [p + "-01" for p in pats] + [p + "-11" for p in pats[:25]]
    er = rng.choice(["Positive", "Negative", "[Not Evaluated]"], len(samples), p=[0.7, 0.25, 0.05])
    pam = rng.choice(["LumA", "LumB", "Basal", "Her2", "Normal", ""], len(samples), p=[.38, .17, .15, .08, .05, .17])
    clin = pd.DataFrame({
        "sampleID": samples,
        "sample_type": ["Primary Tumor" if s.endswith("-01") else "Solid Tissue Normal" for s in samples],
        "breast_carcinoma_estrogen_receptor_status": er, "PAM50Call_RNAseq": pam,
        "age_at_initial_pathologic_diagnosis": rng.integers(30, 90, len(samples)).astype(str),
        "vital_status": rng.choice(["LIVING", "DECEASED"], len(samples), p=[.85, .15]),
    })
    _write(clin, dest / "clinical.tsv", index=False)
    surv = pd.DataFrame({"sample": samples, "_PATIENT": [s[:12] for s in samples],
                         "OS": rng.integers(0, 2, len(samples)).astype(str),
                         "OS.time": rng.integers(30, 4000, len(samples)).astype(str)})
    _write(surv, dest / "survival.tsv", index=False)
    prot_samples = [s for s in samples if rng.random() < 0.8]
    prots = ["ERALPHA", "PR", "HER2", "AKT", "BCL2", "CYCLIN_D1"]
    vals = rng.normal(0, 1, (len(prots), len(prot_samples)))
    er_map = dict(zip(samples, er))
    vals[0] += np.array([1.5 if er_map[s] == "Positive" else -1.0 for s in prot_samples])
    prot = pd.DataFrame(np.round(vals, 4), index=pd.Index(prots, name="Sample"), columns=prot_samples).astype(str)
    _write(prot, dest / "protein_rppa.tsv.gz", index=True)
    genes = ["TP53", "PIK3CA", "GATA3", "CDH1", "MAP3K1", "KMT2C"]
    mut = pd.DataFrame(rng.integers(0, 2, (len(genes), len(samples))), index=pd.Index(genes, name="sample"),
                       columns=samples).astype(str)
    _write(mut, dest / "mutation_gene_level.tsv.gz", index=True)
    cn = pd.DataFrame(rng.integers(-2, 3, (len(genes), len(samples))), index=pd.Index(genes, name="Gene Symbol"),
                      columns=samples).astype(str)
    _write(cn, dest / "copy_number_gistic.tsv.gz", index=True)
    return samples


def make_challenge_repo(root: Path, baseline: Path):
    pack = root / "data" / "tcga-brca"
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "reference_analyses.py").write_text(STAND_IN_ANALYSES)
    with open(pack / "sources.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "sha256"])
        for name in FILES:
            w.writerow([name, hashlib.sha256((baseline / name).read_bytes()).hexdigest()])
    raw = pack / "raw"
    if raw.exists():
        shutil.rmtree(raw)
    shutil.copytree(baseline, raw)


def make_release(baseline: Path, dest: Path, ops: list[dict], seed: int = 1):
    """Copy the baseline and apply our own operations."""
    rnd = random.Random(seed)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(baseline, dest)
    clin = _read(dest / "clinical.tsv", matrix=False)
    er = dict(zip(clin.sampleID, clin.breast_carcinoma_estrogen_receptor_status))
    applied = []
    for op in ops:
        f = dest / op["file"]
        matrix = op["file"].endswith(".gz")
        df = _read(f, matrix)
        if op["type"] == "swap":
            cols = [c for c in df.columns if c.endswith("-01")]
            pos = [c for c in cols if er.get(c) == "Positive"]
            neg = [c for c in cols if er.get(c) == "Negative"]
            a, b = rnd.choice(pos), rnd.choice(neg)
            df[[a, b]] = df[[b, a]].values
            applied.append(("swap", a, b))
        elif op["type"] == "copy_over":
            cols = [c for c in df.columns if c.endswith("-01")]
            for _ in range(op.get("count", 1)):
                tgt, src = rnd.sample(cols, 2)
                df[tgt] = df[src]
                applied.append(("copy_over", tgt, src))
        elif op["type"] == "drop":
            cols = [c for c in df.columns if c.endswith("-01")]
            drop = rnd.sample(cols, op.get("count", 1))
            df = df.drop(columns=drop)
            applied += [("drop", d) for d in drop]
        elif op["type"] == "new_duplicate":
            src = rnd.choice([c for c in df.columns if c.endswith("-01")])
            new = "TCGA-ZZ-9999-01"
            df[new] = df[src]
            applied.append(("new_duplicate", new, src))
        elif op["type"] == "relabel":
            col = op["column"]
            idx = rnd.sample([i for i in df.index if df.at[i, col] not in ("",)], op.get("count", 1))
            for i in idx:
                old = df.at[i, col]
                df.at[i, col] = op["value"] if op["value"] != old else op.get("alt", "LumB")
                applied.append(("relabel", df.at[i, "sampleID"], col, old, df.at[i, col]))
        elif op["type"] == "edit":
            col = rnd.choice([c for c in df.columns])
            df.iloc[0, df.columns.get_loc(col)] = "9" if df.iloc[0, df.columns.get_loc(col)] != "9" else "8"
            applied.append(("edit", col))
        _write(df, f, index=matrix)
    return applied
