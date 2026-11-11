# Cohort Control Tower (featured product, Cohort Firewall track)

**User:** a research engineer responsible for a dataset that gets new releases.
**Workflow they finish:** point the tool at a new TCGA-BRCA release; see what changed, which
protected analyses it affects (and which it doesn't), a readiness verdict per analysis, and a
`findings.json` a reviewer (Repair Review Desk) can act on.

## Run
```bash
python -m cohort_firewall.tower --challenge-repo ~/oncosys-hackathon-challenge \
  --b ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B --out findings.json
python ~/oncosys-hackathon-challenge/format/validate.py findings.json
```
The baseline defaults to the frozen release (`data/tcga-brca/raw`) and is checked against
`sources.csv`. If it doesn't match, every verdict is Insufficient Evidence (TWR-PROV-1).

## How it works
1. **Fingerprint** every sample in every file from its exact text values. Large matrices are
   streamed, so the 64 MB RNA file needs about 65 MB of memory.
2. **Detect changes without being told what to look for:** swaps, profiles copied onto other IDs,
   new IDs carrying existing profiles, samples added or removed, clinical fields changed, values
   lost or edited, and genuine-profile coverage lost per ER status and PAM50 subtype.
3. **Map changes to analyses** using each analysis's input files, the samples it used on the
   baseline, and the clinical columns its code reads. Unaffected analyses are **not rerun**, and the
   output says why.
4. **Verdict per analysis** from `rules/tower_v0_1.yaml`: swaps, duplicates and changed grouping
   labels are Blocked; membership, value and other changes are Conditional; an unverified baseline
   or a failed rerun is Insufficient Evidence; otherwise Ready.
5. **Write `findings.json`** (shared format v0.2): findings with evidence pointers and affected /
   not-affected analyses, before/after results, proposed repairs, human-review flags, limitations,
   and a signed certificate over the release checksums.

## Limitations (shown in the output)
- Exact-match detection: a swap or copy that also alters values is reported as value edits.
- A profile counts as copied only if it was unique in the baseline and most of the sample's values
  changed, so coincidental matches are not accused. This can miss a copy between near-identical profiles.
- The tool shows what changed, not which release is correct. Every repair needs a person's decision.

## Honesty note on the practice release
`make_release.py` defines practice-B's change types in its own header, so they are not secret.
The tool is built to be general and is tested on our own randomized releases (`tests/test_tower.py`)
covering every detector. Judges use an unseen release with different changes.
