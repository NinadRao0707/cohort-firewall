# Results

All results below were produced on the event's frozen TCGA-BRCA release unless marked synthetic.
Each section ends with the commands to reproduce it.

## 1. Release comparison (Cohort Control Tower)

Each release was built with the event's own `make_release.py`, and the tool's `findings.json` was
graded against that release's answer key (`CHANGES.json`) only after the run.

| Release | Changes planted | Found | Unexplained findings | A1 | A2 |
|---|---|---|---|---|---|
| practice-B (public) | 1 protein swap; 5 protein profiles replaced by copies under new IDs | **11 / 11** | 0 | Blocked | Ready, not rerun |
| rehearsal-C | ER relabelled for 3 tumors; 2 protein swaps (ER status not forced to differ) | **5 / 5** | 0 | Blocked | Ready, not rerun |
| rehearsal-D | PAM50 relabelled for 4 tumors; 3 Her2 copy-number profiles replaced | **10 / 10** | 0 | Ready, not rerun | Blocked |
| rehearsal-E | 1 RNA swap; histology relabelled for 2 tumors; 2 Basal protein profiles replaced | **7 / 7** | 0 | Blocked | Ready, not rerun |
| Practice envelope (practice-B without RNA) | as practice-B | **11 / 11** | 0 | Blocked | Ready, not rerun |

What this shows:
- **No change is missed and nothing is invented** across five runs and 44 planted changes.
- **Impact follows the data.** A PAM50 relabel blocks A2 and leaves A1 alone; an ER relabel does the
  opposite; RNA and histology changes are reported but affect neither analysis.
- **Silent changes are named.** On practice-B the protein sample count stays at 747 while 5 samples
  are removed and 5 copies added; the tool reports that a count check alone would miss it.

Each release also produces summary findings (subgroup coverage, count unchanged but membership
changed). They are tagged `x_summary_of_other_findings` and can be left out with `--no-summary-findings`.

**Speed:** unsealing an envelope takes about 2 s; the comparison takes about 14 s the first time
(building the baseline cache) and about 7 s after that.

```bash
bash scripts/rehearse.sh
python -m cohort_firewall.tower --b ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B --out outputs/f.json
python scripts/grade_tower.py outputs/f.json ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B/CHANGES.json
```

## 2. Question readiness on the frozen release

The same release, eight research questions (the example cards in `examples/specs/tcga_*.json`):

| Question | Verdict | Main findings |
|---|---|---|
| ER-alpha protein vs clinical ER status | Conditional | ER-alpha protein missing for 33% of 1,046 eligible tumors (CMP-004) |
| Same, protein-profiled tumors only | **Ready** | 698 tumors, no findings |
| 5-year overall survival | Conditional | 32% followed to 60 months; median follow-up 27.7 months (TIME-002) |
| 2-year progression, fairness across race | **Insufficient Evidence** | Race is not recorded (SUB-001); outcome unknown for 42%; 5.6 events per parameter |
| 2-year progression, fairness across menopause status | Conditional | Peri (39) and Indeterminate (34) too small to evaluate (SUB-002) |
| Counting samples instead of patients | Conditional | 142 patients appear more than once: 1,247 rows for 1,101 patients (UNIT-001) |
| A patient-level risk score | **Blocked** | Out of scope (SCOPE-002) |
| PAM50 subtype mix | Conditional | PAM50 missing for 23% (CMP-004); the two PAM50 calls disagree for 10% (CONS-001) |

### Agreement between sources for the same fact (primary tumors with both values)
| Pair | Disagree |
|---|---|
| ER status: clinical file vs 2012 paper | 0 of 780 |
| PR status: clinical file vs 2012 paper | 0 of 779 |
| PAM50: RNA-seq call vs 2012 microarray call | **52 of 508 (10%)** |
| Vital status (clinical) vs overall-survival event (curated) | 1 of 1,097 |

The organizers quote 11% for the PAM50 disagreement; our denominator is primary tumors that have both calls.

```bash
python data/flatten_tcga.py --challenge-repo ~/oncosys-hackathon-challenge
python scripts/run_tcga_specs.py --save outputs/tcga
```

## 3. Seeded-defect suite (synthetic stand-in cohort)

26 cases on a generated 2,400-patient cohort. Each plants one known problem and must get the
expected verdict and rule. **26 / 26 pass.**

| Group | Cases |
|---|---|
| Question changes the verdict | clean question (Ready), 5-year horizon, treatment recommendation, patient risk score, predictor not in the data, descriptive question with a stray horizon |
| Data problems | hidden leakage, declared leakage, identifiers by name, identifiers by value, small subgroup, too few events, outcome removed, 35% missing HER2, placeholder values, follow-up in days, inconsistent ER sources, impossible ages, an impossible value in an unused field (noted, verdict unchanged) |
| Documentation and access | no dictionary, no license, identifiable data, de-identified patient data (allowed), controlled access, de-identification undeclared |
| Integrity | instruction-like text planted in a cell and the dictionary (verdict unaffected; text never shown) |

Two more checks run with the suite: an edited certificate fails verification, and injected text never
appears in any output.

```bash
python data/make_variants.py && python tests/test_variants.py
```

## 4. Review step

13 rules, all passing: Blocked and Insufficient results can't be approved; conditional approval needs
every finding acknowledged and a note; a result or review edited after signing is refused.

```bash
python tests/test_review.py
```

## 5. Synthetic data at scale (engine testing only)

Synthea breast cancer cohorts, used to check behaviour on a second data source, not for judged results.
A 5,000-woman run gave 157 patients diagnosed since 2012 and only 12 progression events: **Blocked**
(too few events). A 35,000-woman run gave 1,142 patients and 90 events: **Conditional** (27% missing
tumor workup; three race groups too small). Setup: [`SYNTHEA_SETUP.md`](SYNTHEA_SETUP.md).
