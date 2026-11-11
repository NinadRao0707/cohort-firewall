"""Run the protected analyses: decide which are affected by the detected changes, rerun only those.

Analyses come from the event's own data/tcga-brca/reference_analyses.py (A1, A2), loaded from the
challenge repo so results match the organizers' definitions exactly. Any function named a<number>
is picked up; its parameter names say which files it reads.
"""
from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .diff import Change

PARAM_FILES = {
    "clinical": ("clinical.tsv", dict(sep="\t", low_memory=False)),
    "protein": ("protein_rppa.tsv.gz", dict(sep="\t", index_col=0)),
    "survival": ("survival.tsv", dict(sep="\t")),
    "mutation": ("mutation_gene_level.tsv.gz", dict(sep="\t", index_col=0)),
    "copy_number": ("copy_number_gistic.tsv.gz", dict(sep="\t", index_col=0)),
    "rna": ("rna_hiseq.tsv.gz", dict(sep="\t", index_col=0)),
}
# Changes that never touch an analysis's samples on their own
SAMPLELESS = {"features_changed", "file_missing", "file_added"}


@dataclass
class Analysis:
    id: str
    func: object
    params: list[str]
    description: str
    source: str = ""          # function source, used to see which clinical columns it reads

    def reads_column(self, column: str) -> bool:
        return not self.source or f'"{column}"' in self.source or f"'{column}'" in self.source \
            or f".{column}" in self.source

    @property
    def inputs(self) -> list[str]:
        return [PARAM_FILES[p][0] for p in self.params]


@dataclass
class AnalysisRun:
    analysis: Analysis
    before: dict | None = None
    after: dict | None = None
    affected: bool = False
    status: str = "not_rerun"            # shared format: unchanged | changed | not_rerun
    reason: str = ""
    changes: list[Change] = field(default_factory=list)
    error: str = ""


def load_reference_analyses(challenge_repo: Path) -> list[Analysis]:
    path = challenge_repo / "data" / "tcga-brca" / "reference_analyses.py"
    spec = importlib.util.spec_from_file_location("reference_analyses", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = []
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if name[0] == "a" and name[1:].isdigit():
            params = list(inspect.signature(fn).parameters)
            if all(p in PARAM_FILES for p in params):
                doc = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else name
                try:
                    src = inspect.getsource(fn)
                except OSError:
                    src = ""
                out.append(Analysis(name.upper(), fn, params, doc, src))
    return sorted(out, key=lambda a: int(a.id[1:]))


def _run(analysis: Analysis, release_path: Path) -> dict:
    args = []
    for p in analysis.params:
        fname, kw = PARAM_FILES[p]
        args.append(pd.read_csv(release_path / fname, **kw))
    return analysis.func(*args)


def _comparable(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "sample_ids"}


def evaluate_analyses(analyses: list[Analysis], path_a: Path, path_b: Path,
                      changes: list[Change]) -> list[AnalysisRun]:
    runs = []
    for an in analyses:
        run = AnalysisRun(an)
        try:
            run.before = _run(an, path_a)
        except Exception as e:  # baseline must work, or nothing can be concluded
            run.error = f"baseline failed: {type(e).__name__}: {e}"
            runs.append(run)
            continue
        used = set(run.before.get("sample_ids", []))
        used_types = {s[13:15] for s in used}
        relevant = []
        for c in changes:
            if c.file not in an.inputs:
                continue
            if c.type == "coverage_loss":
                continue                  # summarizes other changes; reported, not counted twice
            if c.type == "label_change" and not any(an.reads_column(col) for col in c.detail.get("columns", [])):
                continue                  # this analysis never reads the clinical fields that changed
            if c.type in SAMPLELESS:
                relevant.append(c)
            elif set(c.samples) & used:
                relevant.append(c)
            elif c.type in {"added", "new_duplicate"} and any(s[13:15] in used_types for s in c.samples[:1]):
                relevant.append(c)        # a new sample of a type this analysis includes
        run.changes = relevant
        if not relevant:
            run.reason = ("No change touches this analysis's input files "
                          f"({', '.join(an.inputs)}) for the {len(used)} samples it uses.")
            runs.append(run)
            continue
        run.affected = True
        try:
            run.after = _run(an, path_b)
            same = _comparable(run.before) == _comparable(run.after) and \
                set(run.before.get("sample_ids", [])) == set(run.after.get("sample_ids", []))
            run.status = "unchanged" if same else "changed"
            run.reason = f"Rerun because {len(relevant)} detected change(s) touch its inputs and samples."
        except Exception as e:
            run.error = f"rerun failed: {type(e).__name__}: {e}"
            run.reason = "Affected, but the rerun failed."
        runs.append(run)
    return runs
