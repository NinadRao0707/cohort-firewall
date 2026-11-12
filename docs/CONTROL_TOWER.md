# Cohort Control Tower

Compares a new TCGA-BRCA release with the event's frozen release, finds what changed, reruns only
the analyses it affects, gives each a verdict, and writes `findings.json` in the shared format v0.2.

## Run it
| Situation | Command or click |
|---|---|
| Sealed envelope | Release check → **+ Open envelope** → number and code → **Open and compare** |
| Any folder | `python -m cohort_firewall.tower --b <folder> --out outputs/findings.json` |
| Validate the output | `python ../oncosys-hackathon-challenge/format/validate.py outputs/findings.json` |
| Leave out summary findings | add `--no-summary-findings` |

The baseline defaults to the frozen release (`data/tcga-brca/raw` in the challenge repository) and is
checked against `sources.csv`. If it doesn't match, every verdict is Insufficient Evidence (TWR-PROV-1).

## How it works
1. **Fingerprint every sample in every file** from its exact text values. Large matrices are streamed,
   so even the 64 MB RNA file needs little memory. Baseline fingerprints are cached by file checksum.
2. **Compare only the files the new release has.** A baseline file the release doesn't carry (envelopes
   have no RNA) is listed as "not compared", not reported as a change.
3. **Detect changes without being told what to look for** (table below).
4. **Map changes to analyses** by input file, by the samples each analysis used on the baseline, and by
   the clinical columns its code reads. Unaffected analyses are not rerun; the output says why.
5. **Rerun affected analyses** with the event's own `reference_analyses.py`, and show before and after values.
6. **Give each analysis a verdict** from [`rules/tower_v0_1.yaml`](../rules/tower_v0_1.yaml).
7. **Write `findings.json`** with findings, evidence, affected and unaffected analyses, proposed repairs,
   limitations, a plain-English summary, ranked next steps and a signed certificate.

## What it detects
| Change | Finding kind | Proposed repair |
|---|---|---|
| Two samples exchanged profiles | `sample_swap` | Restore both from the baseline |
| A sample now carries another sample's exact profile | `duplicate` | Restore from the baseline |
| A new sample ID carries an existing profile | `duplicate` | Exclude the new ID |
| Samples removed or added | `membership_change` | Flag for review |
| Sample count unchanged but membership changed | `membership_change` (summary) | – |
| Clinical field changed for a sample | `label_conflict` | Flag for review |
| Values lost or edited | `missing_data` / `other` | Flag for review |
| Fewer genuine profiles in an ER or PAM50 subgroup | `missing_data` (summary) | – |

A profile counts as copied only if it was unique in the baseline and most of the sample's values
changed, so samples that happen to share values are never accused.

**Evidence cites only samples that changed.** For a copy, the sample whose profile was copied is
unchanged: it is named in the evidence note and the summary, never cited as a changed sample.

## Severity
Each finding is rated by how much it could change a protected analysis's answer, and the reason is
written into the finding (`x_severity_reason`), with the analysis's headline value before and after
when it was rerun.

| Severity | When |
|---|---|
| High | A swap, a copy, or a change to a label an analysis groups by, in samples a protected analysis uses |
| Medium | The same kinds of change in data no protected analysis uses; samples added, removed or edited in an analysis's data; a subgroup losing 5% or more of its genuine profiles |
| Low | Changes no protected analysis reads; small subgroup losses; non-key clinical fields |

Example: *"High: measurements are attached to the wrong samples in data A1 uses, so its result can't be
trusted (A1 difference 3.051 → 3.019)."*

## Verdict rules
| Rule | Verdict | When |
|---|---|---|
| TWR-PROV-1 | Insufficient Evidence | The baseline doesn't match the frozen checksums |
| TWR-RUN-1 | Insufficient Evidence | The analysis couldn't be run |
| TWR-SWAP-1 | Blocked | A swap touches the analysis's samples |
| TWR-DUP-1 | Blocked | A copied profile touches the analysis's samples |
| TWR-LBL-1 | Blocked | A clinical label the analysis groups by changed |
| TWR-MEM-1 | Conditional | Samples appeared or disappeared |
| TWR-VAL-1 | Conditional | Values edited or lost |
| TWR-OTH-1 | Conditional | Other changes to its input files |
| TWR-RES-1 | Conditional | The result changed with no integrity issue |

## Limitations
- Exact-match detection: a swap or copy that also edits values is reported as value edits.
- The tool shows what changed, not which release is correct; every repair needs a person's decision.
- Coverage per subgroup uses the newer release's labels.
