# Design notes

## Verdicts (precedence: worst wins)

| Verdict | Meaning | Typical trigger |
|---|---|---|
| BLOCKED | A check ran and found a hard failure for this question | Identifiers present, outcome absent, clinical-decision use, too few events |
| INSUFFICIENT_EVIDENCE | The firewall could not verify something it needs | No dictionary, unknown license or provenance, a check could not run |
| CONDITIONAL | Usable for this question if listed remedies are applied | Leakage suspects, small subgroups, 20–50% missingness, short follow-up |
| READY | Every applicable check passed under the current policy | |

Blocked vs Insufficient Evidence is the distinction judges will probe:
Blocked = "we checked and it fails". Insufficient = "we could not check, so we do not pass it".

## Default-deny, in code
- Spec fails validation → INSUFFICIENT_EVIDENCE (no guessing what the user meant)
- A check errors or cannot run → INSUFFICIENT_EVIDENCE
- A check never reports → INSUFFICIENT_EVIDENCE
- A rule references a metric its check did not produce → INSUFFICIENT_EVIDENCE

## Checks (all deterministic)

| Check | Measures | Rules |
|---|---|---|
| metadata | dictionary present, license, provenance, real-patient flag, undocumented columns | META-001..006 |
| scope | intended use; keyword backstop for individual care decisions | SCOPE-001..002 |
| spec_quality | parser confidence | SPEC-001 |
| columns | outcome, predictors, filter and time columns present | COL-001..004 |
| cohort | size after population filters | COH-001 |
| completeness | outcome and worst-predictor missingness | CMP-001..004 |
| outcome_events | events, minority class, events per model parameter | EVT-001..002 |
| leakage | dictionary-declared post-index predictors; single-feature AUC ≥ 0.95 | LEAK-001..002 |
| temporal | share of cohort observed through the question's horizon | TIME-001..002 |
| subgroups | requested subgroup columns present; categories below minimum n | SUB-001..002 |
| phi | identifier-like column names and values (SSN, phone, email, full dates, ZIP) | PHI-001 |
| injection | instruction-like text in cells, column names, dictionary | INJ-001 |

Thresholds live in the YAML, are hackathon defaults, and are stated as such in the pitch.
Grounding to cite: METRIC framework (fitness for a specific purpose, npj Digit Med 2024) and
STANDING Together recommendations (dataset transparency and subgroup representation, 2024).

## Threat model (the "firewall" part)
- **Prompt injection via data.** Dataset text is never sent raw to an LLM. Only sanitized
  identifiers, metric values and rule reasons reach the report writer. Flagged text is reported
  by location only. The verdict comes from rules, so injected text cannot change it.
- **LLM drift.** Report text is rejected and replaced by the template if it omits the verdict or
  any Blocked/Insufficient rule id, or states a different verdict.
- **Parser mislabels clinical use.** A deterministic keyword guard (SCOPE-002) backs up the parser.
- **Tampering after the fact.** Certificates bind dataset, dictionary, spec, policy file hash and
  engine version, signed with Ed25519. Changing any byte fails verification.
- **Data retention.** The API evaluates uploads in memory and stores hashes and results only;
  the Supabase table is append-only.

## Known limits (say these before judges do)
- PHI detection is heuristic; a pass is not a privacy guarantee.
- Single-feature AUC catches blatant leakage, not leakage spread across several features.
- Events-per-parameter ≥ 10 is a rough rule of thumb, not a sample-size calculation.
- Subgroup check uses a minimum count; it does not compare against a reference population.
