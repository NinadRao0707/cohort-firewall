"""How much does a change matter, and do the repairs fix it?

1. Bigger than noise? Bootstrap the organizers' own analysis code on the baseline (resampling the
   samples it used) to get the shift you'd see from sampling alone. Report the observed shift as a
   multiple of that noise. A scalar result (A1's difference) uses the bootstrap standard error;
   a distribution (A2's subtype mix) uses total variation distance against its 95th percentile.
2. Do the repairs work? Apply the proposed repairs to the new release in memory (restore changed
   samples from the baseline, drop copies) and rerun. Then repair one kind of change at a time to
   attribute the shift: which problem accounts for how much of it.

Size is reported, never used to clear a problem: a swap that barely moves a mean is still a swap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .analyses import PARAM_FILES

B_DEFAULT = 150


def _load(run, path):
    return {p: pd.read_csv(path / PARAM_FILES[p][0], **PARAM_FILES[p][1]) for p in run.analysis.params}


def _id_col(df):
    return "sampleID" if "sampleID" in df.columns else ("sample" if "sample" in df.columns else None)


def _resample(frames: dict, ids: list[str], rng) -> dict:
    """Bootstrap: draw the analysis's own samples with replacement, giving each copy a unique ID that
    keeps the TCGA sample-type digits, so the organizers' code treats it like the original."""
    picks = rng.choice(ids, size=len(ids), replace=True)
    new_ids = [f"{s}#{i}" for i, s in enumerate(picks)]
    out = {}
    for p, df in frames.items():
        col = _id_col(df) if p in ("clinical", "survival") else None
        if col:
            d = df.drop_duplicates(col).set_index(col)
            keep = [s for s in picks if s in d.index]
            sub = d.loc[keep].copy()
            sub.index = [n for s, n in zip(picks, new_ids) if s in d.index]
            out[p] = sub.rename_axis(col).reset_index()
        else:
            keep = [(s, n) for s, n in zip(picks, new_ids) if s in df.columns]
            sub = df[[s for s, _ in keep]].copy()
            sub.columns = [n for _, n in keep]
            out[p] = sub
    return out


def _metric(result: dict):
    if "difference" in result:
        return "difference", "scalar"
    if isinstance(result.get("percent"), dict) and result["percent"]:
        return "percent", "distribution"
    for k, v in result.items():
        if isinstance(v, dict) and v and all(isinstance(x, (int, float)) for x in v.values()):
            return k, "distribution"
    for k, v in result.items():
        if isinstance(v, (int, float)) and not k.startswith("n_"):
            return k, "scalar"
    return None, None


def _tvd(p: dict, q: dict) -> float:
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in keys)


def _value(result, key, kind, base=None):
    return result.get(key) if kind == "scalar" else _tvd(result.get(key, {}), base.get(key, {}))


def noise(run, path_a, B: int = B_DEFAULT, seed: int = 0) -> dict | None:
    key, kind = _metric(run.before or {})
    ids = (run.before or {}).get("sample_ids") or []
    if not key or not run.after or len(ids) < 10:
        return None
    frames = _load(run, path_a)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B):
        try:
            r = run.analysis.func(**_resample(frames, ids, rng))
            vals.append(_value(r, key, kind, run.before))
        except Exception:
            continue
    if len(vals) < B // 2:
        return None
    vals = np.array(vals, dtype=float)
    if kind == "scalar":
        b, a = float(run.before[key]), float(run.after[key])
        se = float(vals.std(ddof=1))
        lo, hi = np.percentile(vals, [2.5, 97.5])
        ratio = abs(a - b) / se if se > 0 else float("inf")
        out = {"metric": key, "kind": kind, "before": b, "after": a, "delta": round(a - b, 4),
               "noise": round(se, 4), "noise_name": "bootstrap standard error",
               "baseline_ci95": [round(float(lo), 4), round(float(hi), 4)],
               "after_inside_baseline_ci": bool(lo <= a <= hi), "sign_flipped": (a > 0) != (b > 0)}
    else:
        obs = _tvd(run.after.get(key, {}), run.before.get(key, {}))
        q95 = float(np.percentile(vals, 95))
        ratio = obs / q95 if q95 > 0 else float("inf")
        out = {"metric": key, "kind": kind, "shift": round(obs, 2), "unit": "percentage points (total variation)",
               "noise": round(q95, 2), "noise_name": "95th percentile of resampling shifts"}
    out["ratio"] = round(ratio, 2)
    out["label"] = ("within sampling noise" if ratio < 1 else "borderline" if ratio < 2 else "beyond sampling noise")
    out["bootstrap_draws"] = int(len(vals))
    return out


def _restore(frames_b: dict, frames_a: dict, file_samples: dict[str, set]) -> dict:
    """Restore the given samples, per file, to their baseline state (present -> baseline values,
    absent from the baseline -> removed)."""
    out = {}
    for p, df in frames_b.items():
        fname = PARAM_FILES[p][0]
        samples = file_samples.get(fname, set())
        if not samples:
            out[p] = df
            continue
        a = frames_a[p]
        col = _id_col(df) if p in ("clinical", "survival") else None
        if col:
            d = df.drop_duplicates(col).set_index(col)
            ai = a.drop_duplicates(col).set_index(col)
            d = d.drop(index=[s for s in samples if s in d.index])
            back = ai.loc[[s for s in samples if s in ai.index]]
            out[p] = pd.concat([d, back.reindex(columns=d.columns)]).rename_axis(col).reset_index()
        else:
            d = df.drop(columns=[s for s in samples if s in df.columns])
            back = a[[s for s in samples if s in a.columns]].reindex(d.index)
            out[p] = pd.concat([d, back], axis=1)
    return out


def repair_simulation(run, path_a, path_b, findings: list[dict]) -> dict | None:
    """Rerun the analysis with all repairs, then with one kind of repair at a time."""
    key, kind = _metric(run.before or {})
    if not key or not run.after:
        return None
    relevant = [f for f in findings if run.analysis.id in (f.get("affects_analyses") or [])
                and not f.get("x_summary_of_other_findings")]
    if not relevant:
        return None
    fa, fb = _load(run, path_a), _load(run, path_b)

    def samples_of(fs):
        out: dict[str, set] = {}
        for f in fs:
            for e in f.get("evidence", []):
                if e.get("kind") == "sample" and e.get("file"):
                    out.setdefault(e["file"], set()).add(e["id"])
        return out

    def val(frames):
        return _value(run.analysis.func(**frames), key, kind, run.before)

    before_v = _value(run.before, key, kind, run.before)
    after_v = _value(run.after, key, kind, run.before)
    total = after_v - before_v
    fixed_all = val(_restore(fb, fa, samples_of(relevant)))
    by_kind: dict[str, list] = {}
    for f in relevant:
        by_kind.setdefault(f.get("kind", "other"), []).append(f)
    parts = []
    for k, fs in by_kind.items():
        v = val(_restore(fb, fa, samples_of(fs)))
        share = (after_v - v) / total if total else 0.0
        parts.append({"kind": k, "findings": [f["id"] for f in fs], "value_if_only_this_is_fixed": round(v, 4),
                      "share_of_shift_pct": abs(round(100 * share)) if abs(share) < 0.005 else round(100 * share)})
    parts.sort(key=lambda x: -abs(x["share_of_shift_pct"]))
    tol = 1e-6 if kind == "scalar" else 0.05
    return {"metric": key if kind == "scalar" else f"{key} shift (TVD, points)",
            "baseline": round(before_v, 4), "new_release": round(after_v, 4),
            "after_all_repairs": round(fixed_all, 4),
            "back_to_baseline": abs(fixed_all - before_v) <= tol,
            "by_kind": parts}


KIND_WORDS = {"sample_swap": "the swaps", "duplicate": "the copied profiles", "membership_change": "the removals",
              "label_conflict": "the relabels", "missing_data": "the lost values", "other": "the other edits"}


def sentence(aid: str, m: dict | None, rep: dict | None, verdict: str = "") -> str:
    parts = []
    if m:
        if m["kind"] == "scalar":
            parts.append(f"{aid}'s {m['metric']} moved {m['delta']:+g} ({m['before']:g} → {m['after']:g}), "
                         f"{m['ratio']:g}× its sampling noise ({m['noise_name']} {m['noise']:g}): {m['label']}.")
        else:
            parts.append(f"{aid}'s {m['metric']} mix shifted {m['shift']:g} points, {m['ratio']:g}× what resampling "
                         f"alone produces: {m['label']}.")
        if m["label"] != "beyond sampling noise" and verdict in ("Blocked", "Conditional"):
            parts.append("A small shift doesn't make it safe: the verdict comes from what changed, not how much, "
                         "and another analysis of the same samples could move further.")
    if rep:
        top = rep["by_kind"][0] if rep["by_kind"] else None
        if top and len(rep["by_kind"]) > 1:
            parts.append(f"{KIND_WORDS.get(top['kind'], top['kind']).capitalize()} account for "
                         f"{top['share_of_shift_pct']:.0f}% of the shift.")
        parts.append("With all proposed repairs applied it returns to its baseline value."
                     if rep["back_to_baseline"] else
                     f"With all proposed repairs applied it is {rep['after_all_repairs']:g} (baseline {rep['baseline']:g}).")
    return " ".join(parts)
