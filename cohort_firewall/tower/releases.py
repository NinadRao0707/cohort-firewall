"""Load a TCGA-BRCA release directory and fingerprint every sample in every file.

All values are read as their original text (no float parsing), so a fingerprint changes only
when the text of a value changes. Matrix files (genes/proteins x samples, up to 64 MB) are
fingerprinted by streaming line by line, keeping only one hash per sample in memory; full
values are read back only for the few samples that changed.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# file -> (orientation, id column for row-oriented files)
LAYOUT = {
    "clinical.tsv": ("rows", "sampleID"),
    "survival.tsv": ("rows", "sample"),
    "protein_rppa.tsv.gz": ("columns", None),
    "mutation_gene_level.tsv.gz": ("columns", None),
    "copy_number_gistic.tsv.gz": ("columns", None),
    "rna_hiseq.tsv.gz": ("columns", None),
}
MISSING = {"", "NA", "NaN", "nan", "null", "[Not Available]", "[Not Evaluated]", "[Unknown]",
           "[Not Applicable]", "[Discrepancy]", "'--", "--"}
SEP = "\x1f"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_sha256(path: Path) -> str:
    """Hash of decompressed content, as the event's make_release.py uses for generated releases."""
    opener = gzip.open if path.suffix == ".gz" else open
    h = hashlib.sha256()
    with opener(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fp(values) -> str:
    return hashlib.sha256(SEP.join(values).encode()).hexdigest()[:20]


def _open_text(path: Path):
    return gzip.open(path, "rt", newline="") if path.suffix == ".gz" else open(path, newline="")


@dataclass
class FileView:
    name: str
    path: Path
    orientation: str
    features: list[str]
    samples: list[str]                       # in file order, first occurrence kept
    fingerprints: dict[str, str] = field(default_factory=dict)
    empty: set[str] = field(default_factory=set)
    _rows: pd.DataFrame | None = None        # row files only (small)
    idcol: str | None = None

    def values(self, sids) -> dict[str, list[str]]:
        """Full text values for the given samples, aligned to self.features."""
        sids = [s for s in dict.fromkeys(sids) if s in self.fingerprints]
        if not sids:
            return {}
        if self.orientation == "rows":
            return {s: list(self._rows.loc[s]) for s in sids}
        want = set(sids)
        with _open_text(self.path) as f:
            header = f.readline().rstrip("\n").split("\t")
            pos = {}
            for i, c in enumerate(header[1:], 1):
                if c in want and c not in pos:
                    pos[c] = i
            out = {s: [] for s in pos}
            for line in f:
                parts = line.rstrip("\n").split("\t")
                for s, i in pos.items():
                    out[s].append(parts[i] if i < len(parts) else "")
        return out


@dataclass
class Release:
    name: str
    path: Path
    files: dict[str, FileView]
    file_hashes: dict[str, dict]


def _load_rows(p: Path, fname: str, idcol: str) -> FileView:
    df = pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)
    if idcol not in df.columns:
        idcol = df.columns[0]
    df = df.set_index(idcol)
    df = df[~df.index.duplicated(keep="first")]
    v = FileView(fname, p, "rows", list(df.columns), list(df.index), _rows=df, idcol=idcol)
    for sid, row in zip(df.index, df.itertuples(index=False, name=None)):
        v.fingerprints[sid] = _fp(row)
        if all(x.strip() in MISSING for x in row):
            v.empty.add(sid)
    return v


def _load_matrix_numeric(p: Path, fname: str) -> FileView:
    """Fast path for all-numeric matrices: pandas' C parser to float64, then one hash per sample column
    over its raw bytes. Same idea as the text fingerprint (any edit, move or loss changes it), but the
    work runs in compiled code. Raises ValueError on any non-numeric cell, so the caller falls back."""
    import numpy as np
    with _open_text(p) as f:
        header = f.readline().rstrip("\n").split("\t")
    cols = header[1:]
    first: dict[str, int] = {}
    for i, c in enumerate(cols):
        first.setdefault(c, i)
    keep = sorted(first.values())
    df = pd.read_csv(p, sep="\t", header=None, skiprows=1, usecols=[0] + [i + 1 for i in keep],
                     index_col=0, dtype={0: str}, engine="c")
    arr = df.to_numpy()
    if arr.dtype.kind not in "fiub":
        raise ValueError("non-numeric values")
    arr = np.ascontiguousarray(arr.astype(np.float64).T) + 0.0      # +0.0 turns -0.0 into 0.0
    samples = [cols[i] for i in keep]
    v = FileView(fname, p, "columns", [str(x) for x in df.index], samples)
    empty = np.isnan(arr).all(axis=1)
    for j, s_id in enumerate(samples):
        v.fingerprints[s_id] = hashlib.blake2b(arr[j].tobytes(), digest_size=16).hexdigest()
        if empty[j]:
            v.empty.add(s_id)
    return v


def _load_any_matrix(p: Path, fname: str) -> FileView:
    try:
        return _load_matrix_numeric(p, fname)
    except (ValueError, TypeError):
        return _load_matrix(p, fname)


def _load_matrix(p: Path, fname: str) -> FileView:
    with _open_text(p) as f:
        header = f.readline().rstrip("\n").split("\t")
        cols = header[1:]
        first = {}
        for i, c in enumerate(cols):
            first.setdefault(c, i)
        keep = sorted(first.values())
        hashers = [hashlib.sha256() for _ in keep]
        nonmissing = [False] * len(keep)
        features = []
        for line in f:
            parts = line.rstrip("\n").split("\t")
            features.append(parts[0])
            vals = parts[1:]
            for j, i in enumerate(keep):
                x = vals[i] if i < len(vals) else ""
                hashers[j].update((x + SEP).encode())
                if not nonmissing[j] and x.strip() not in MISSING:
                    nonmissing[j] = True
    samples = [cols[i] for i in keep]
    v = FileView(fname, p, "columns", features, samples)
    for j, s in enumerate(samples):
        v.fingerprints[s] = hashers[j].hexdigest()[:20]
        if not nonmissing[j]:
            v.empty.add(s)
    return v


CACHE_VERSION = "fp2"


def load_release(path: str | Path, name: str | None = None, include_rna: bool = True,
                 cache_dir: Path | None = None, only: set[str] | None = None) -> Release:
    """Load and fingerprint a release. With cache_dir, a release whose files are byte-identical
    to a previous load (same sha256 per file) is read from the cache instead of re-fingerprinted."""
    import pickle
    path = Path(path)
    if cache_dir is not None:
        present = [f for f in LAYOUT if (path / f).exists() and (include_rna or not f.startswith("rna_"))
                   and (only is None or f in only)]
        key = hashlib.sha256("|".join([CACHE_VERSION] + [f"{f}:{file_sha256(path / f)}" for f in present])
                             .encode()).hexdigest()[:24]
        cached = Path(cache_dir) / f"release-{key}.pkl"
        if cached.exists():
            rel = pickle.loads(cached.read_bytes())
            rel.name, rel.path = name or path.name, path
            for v in rel.files.values():
                v.path = path / v.name
            return rel
        rel = load_release(path, name, include_rna, only=only)
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        cached.write_bytes(pickle.dumps(rel))
        return rel
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(fname, orient, idcol) for fname, (orient, idcol) in LAYOUT.items()
            if (path / fname).exists() and not (fname.startswith("rna_") and not include_rna)
            and (only is None or fname in only)]

    def work(job):
        fname, orient, idcol = job
        p = path / fname
        view = _load_rows(p, fname, idcol) if orient == "rows" else _load_any_matrix(p, fname)
        return fname, {"file": file_sha256(p), "content": content_sha256(p)}, view

    # Files are read in parallel: decompression and pandas' parser release the GIL for most of the work.
    with ThreadPoolExecutor(max_workers=max(1, min(6, len(jobs)))) as pool:
        results = list(pool.map(work, jobs))
    files = {f: v for f, _, v in results}
    hashes = {f: h for f, h, _ in results}
    return Release(name or path.name, path, files, hashes)


def frozen_checksums(challenge_repo: Path) -> dict[str, str]:
    src = challenge_repo / "data" / "tcga-brca" / "sources.csv"
    return {r["file"]: r["sha256"] for r in csv.DictReader(open(src))} if src.exists() else {}
