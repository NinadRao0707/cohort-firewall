"""Detect what changed between two releases, sample by sample, without being told what to look for.

Detected change types (shared-format kinds in brackets):
  swap            two samples exchanged profiles                         [sample_swap]
  copied_profile  a sample now carries another sample's exact profile    [duplicate]
  new_duplicate   a new sample ID carries an existing sample's profile    [duplicate]
  removed / added samples that disappeared / appeared                    [membership_change]
  label_change    clinical fields changed for a sample                   [label_conflict / other]
  values_missing  values that existed are now missing                    [missing_data]
  values_edited   values changed in place                                [other]
  coverage_loss   fewer genuine profiles in a clinical subgroup          [missing_data]
  count_masks_membership  same sample count, different samples           [membership_change]

Fingerprints are exact. A swap combined with small edits shows up as two value edits, not a swap;
that limitation is reported with every finding. Only profiles that were unique in the baseline count
as copies or swaps, and only when most of the sample's values changed; a sample whose few edited
fields happen to match another sample is reported as an edit, not a copy.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .releases import MISSING, Release, _fp

KEY_LABELS = {
    "breast_carcinoma_estrogen_receptor_status", "breast_carcinoma_progesterone_receptor_status",
    "lab_proc_her2_neu_immunohistochemistry_receptor_status", "PAM50Call_RNAseq", "sample_type",
    "pathologic_stage", "AJCC_Stage_nature2012", "vital_status",
}
SUBGROUP_COLUMNS = ["breast_carcinoma_estrogen_receptor_status", "PAM50Call_RNAseq"]


@dataclass
class Change:
    type: str
    file: str
    samples: list[str]
    detail: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return {"swap": "sample_swap", "copied_profile": "duplicate", "new_duplicate": "duplicate",
                "removed": "membership_change", "added": "membership_change",
                "values_missing": "missing_data", "coverage_loss": "missing_data",
                "count_masks_membership": "membership_change",
                "label_change": "label_conflict" if self.detail.get("key_labels") else "other",
                }.get(self.type, "other")


def _missing(v: str) -> bool:
    return v.strip() in MISSING


def diff_file(a, b) -> list[Change]:
    """Compare one file between releases, using fingerprints first and full values only for changed samples."""
    changes: list[Change] = []
    same_features = a.features == b.features
    if not same_features:
        changes.append(Change("features_changed", a.name, [], {
            "removed": sorted(set(a.features) - set(b.features))[:20],
            "added": sorted(set(b.features) - set(a.features))[:20]}))
        common = [f for f in a.features if f in set(b.features)]
        # Re-fingerprint on the shared features so unchanged samples still match.
        ia = {f: i for i, f in enumerate(a.features)}
        ib = {f: i for i, f in enumerate(b.features)}
        va_all, vb_all = a.values(a.samples), b.values(b.samples)
        fa = {s: _fp([v[ia[f]] for f in common]) for s, v in va_all.items()}
        fb = {s: _fp([v[ib[f]] for f in common]) for s, v in vb_all.items()}
        get_a = lambda ids: {s: [va_all[s][ia[f]] for f in common] for s in ids if s in va_all}
        get_b = lambda ids: {s: [vb_all[s][ib[f]] for f in common] for s in ids if s in vb_all}
        empty_a = {s for s, v in get_a(fa).items() if all(_missing(x) for x in v)}
        empty_b = {s for s, v in get_b(fb).items() if all(_missing(x) for x in v)}
    else:
        common = a.features
        fa, fb = a.fingerprints, b.fingerprints
        get_a, get_b = a.values, b.values
        empty_a, empty_b = a.empty, b.empty

    inv_a = defaultdict(set)
    for s, h in fa.items():
        if s not in empty_a:
            inv_a[h].add(s)

    A, B = set(fa), set(fb)
    changed = sorted(s for s in A & B if fa[s] != fb[s])
    vals_a, vals_b = get_a(changed), get_b(changed)
    done = set()
    for sid in changed:
        if sid in done:
            continue
        owners = inv_a.get(fb[sid], set()) if sid not in empty_b else set()
        sources = owners - {sid} if len(owners) == 1 else set()
        va, vb = vals_a[sid], vals_b[sid]
        # A sample that differs from its own previous profile in only a few values was edited or
        # relabelled; landing on another sample's profile by coincidence is not a copy.
        idx = [i for i in range(len(va)) if va[i] != vb[i]]
        if len(idx) <= max(2, int(0.1 * len(common))):
            sources = set()
        if sources:
            other = sorted(sources)[0]
            if other in B and fb[other] == fa[sid]:
                changes.append(Change("swap", a.name, [sid, other]))
                done |= {sid, other}
            else:
                changes.append(Change("copied_profile", a.name, [sid, other], {"carries_profile_of": other}))
                done.add(sid)
            continue
        feats = [common[i] for i in idx]
        newly_missing = [common[i] for i in idx if not _missing(va[i]) and _missing(vb[i])]
        if a.name == "clinical.tsv":
            changes.append(Change("label_change", a.name, [sid], {
                "columns": feats[:20], "key_labels": sorted(set(feats) & KEY_LABELS),
                "before": {common[i]: va[i] for i in idx[:10]},
                "after": {common[i]: vb[i] for i in idx[:10]}}))
        elif newly_missing and len(newly_missing) == len(idx):
            changes.append(Change("values_missing", a.name, [sid], {"n_values": len(idx), "features": feats[:10]}))
        else:
            changes.append(Change("values_edited", a.name, [sid], {
                "n_values": len(idx), "n_newly_missing": len(newly_missing), "features": feats[:10]}))
        done.add(sid)

    for sid in sorted(B - A):
        owners = inv_a.get(fb[sid], set()) if sid not in empty_b else set()
        if len(owners) == 1:
            src = next(iter(owners))
            changes.append(Change("new_duplicate", a.name, [sid, src], {"carries_profile_of": src}))
        else:
            changes.append(Change("added", a.name, [sid]))
    for sid in sorted(A - B):
        changes.append(Change("removed", a.name, [sid]))
    if len(A) == len(B) and A != B:
        changes.append(Change("count_masks_membership", a.name, sorted(A ^ B), {
            "n": len(A), "removed": len(A - B), "added": len(B - A)}))
    return changes


def _genuine_pair(a: Release, b: Release, fname: str) -> tuple[set[str], set[str]]:
    """Samples with a real profile of their own: every non-empty sample in the baseline; in the new
    release, non-empty samples whose profile is not another sample's baseline profile."""
    va, vb = a.files[fname], b.files[fname]
    ga = {s for s in va.fingerprints if s not in va.empty}
    owner = defaultdict(set)
    for s, h in va.fingerprints.items():
        if s not in va.empty:
            owner[h].add(s)
    gb = set()
    for s, h in vb.fingerprints.items():
        if s in vb.empty:
            continue
        others = owner.get(h, set()) - {s}
        if others and va.fingerprints.get(s) != h:
            continue                      # carries someone else's measurement
        gb.add(s)
    return ga, gb


def coverage_changes(a: Release, b: Release) -> list[Change]:
    """Genuine-profile counts per clinical subgroup, per file, release A vs B."""
    clin = b.files.get("clinical.tsv") or a.files.get("clinical.tsv")
    if clin is None:
        return []
    out = []
    rows = clin._rows
    for col in SUBGROUP_COLUMNS:
        if col not in clin.features:
            continue
        label = {s: v for s, v in rows[col].items() if not _missing(v)}
        for fname in sorted(set(a.files) & set(b.files)):
            if fname == "clinical.tsv":
                continue
            ga, gb = _genuine_pair(a, b, fname)
            groups = sorted({label[s] for s in ga | gb if s in label})
            for g in groups:
                na = sum(1 for s in ga if label.get(s) == g)
                nb = sum(1 for s in gb if label.get(s) == g)
                if nb < na:
                    lost = sorted(s for s in ga - gb if label.get(s) == g)
                    out.append(Change("coverage_loss", fname, lost, {
                        "subgroup_column": col, "subgroup": g, "before": na, "after": nb}))
    return out


def diff_releases(a: Release, b: Release) -> list[Change]:
    changes = []
    for fname in sorted(set(a.files) | set(b.files)):
        if fname not in b.files:
            changes.append(Change("file_missing", fname, [], {"missing_in": b.name}))
        elif fname not in a.files:
            changes.append(Change("file_added", fname, [], {"missing_in": a.name}))
        else:
            changes.extend(diff_file(a.files[fname], b.files[fname]))
    return changes + coverage_changes(a, b)
