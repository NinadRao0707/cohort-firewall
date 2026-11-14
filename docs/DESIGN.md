# Design

## Principles
1. **Checks measure; rules decide.** Checks produce numbers. A versioned YAML rule file turns those
   numbers into findings and a verdict. Anyone can read the rules; no code change is needed to adjust one.
2. **Nothing passes by default.** A check that can't run, a missing input, or an unverified source is
   Insufficient Evidence, never Ready.
3. **Readiness belongs to the data and the question together.** A problem in a field the question
   doesn't use is reported as a note, not counted against the verdict.
4. **A person decides.** The tool recommends; approval is a recorded human step.
5. **A language model never decides.** Optional AI only turns plain English into filters or words a report.

## Verdicts
Worst finding wins: Blocked > Insufficient Evidence > Conditional > Ready.

| Verdict | Meaning | Typical cause |
|---|---|---|
| **Blocked** | A check ran and found a problem this question can't work around | Identifiers, outcome missing, out-of-scope use, too few events |
| **Insufficient Evidence** | The tool can't confirm something the question needs | No dictionary, unknown license, attribute not recorded |
| **Conditional** | Usable after the listed fixes are made and reported | Missing values, short follow-up, small subgroups, disagreeing sources |
| **Ready** | Every applicable check passed | |

## The research-question card
| Field | Example |
|---|---|
| Question | "Is this release suitable for a 5-year survival study?" |
| Intended use | Research analysis, research model, or the two clinical uses (always Blocked) |
| Who is studied | `sample_type` is Primary Tumor; `er_status` is Positive or Negative |
| Outcome | Kind of question, outcome field, follow-up field, time horizon |
| Predictors | Fields the analysis uses |
| Fairness across | Attributes to check subgroup coverage for, including ones not in the data |
| Acceptable limitations | Conditional rules the use can tolerate (see below) |

## Checks (question readiness)
| Check | What it looks for | Rules |
|---|---|---|
| Documentation and license | Dictionary, license, provenance, patient-data status, verified source files, undocumented fields | META-001 to META-009 |
| Permitted use | Clinical intended use; wording that asks for a diagnosis, treatment or patient risk score | SCOPE-001, SCOPE-002 |
| Question clarity | Parser confidence | SPEC-001 |
| Required fields | Outcome, predictors, group fields, follow-up time present | COL-001 to COL-004 |
| Group being studied | Records match the group | COH-001 |
| Missing values | Outcome and predictor missingness | CMP-001 to CMP-004 |
| Enough outcome events | Events and events per model parameter | EVT-001, EVT-002 |
| Unfair shortcuts | Fields recorded after the outcome; a single field that separates the outcome almost perfectly | LEAK-001, LEAK-002 |
| Follow-up length | Share observed through the horizon; negative times | TIME-001 to TIME-003 |
| Patients counted once | More than one row per patient | UNIT-001 |
| Subgroup coverage | Fairness attribute missing; groups too small to evaluate | SUB-001, SUB-002 |
| Records agree across sources | Two sources for the same fact that disagree | CONS-001 |
| Plausible values | Values outside the dictionary's declared ranges | PLAUS-001 |
| Direct identifiers | Identifier-like field names and values | PHI-001 |
| Instruction-like text | Text that tries to instruct an AI, reported by location only | INJ-001 |

Thresholds are defaults in [`rules/policy_v0_1.yaml`](../rules/policy_v0_1.yaml) (version 0.5.1):
10 events per parameter, 50 records per subgroup, 20% and 50% missingness, 5% source disagreement.

**Why 20% and 50% for missing values.** These are our defaults, not a published standard; no single
agreed threshold exists. They sit within the range the literature quotes: Jakobsen et al. (2017)
give a rule of thumb that results with 40% or more missing in important variables should be treated
as hypothesis-generating only, and Madley-Dowd et al. (2019) summarise guidance that bias is likely
above 10% missing, while showing that such cut-offs have a limited evidence base and that the reason
data are missing matters more than the amount. So the tool asks for a handling plan above 20%, blocks
above 50%, shows each measured rate with a 95% range, and asks why the data are missing.

- Jakobsen JC, Gluud C, Wetterslev J, Winkel P. *BMC Med Res Methodol.* 2017;17:162. doi:10.1186/s12874-017-0442-1
- Madley-Dowd P, Hughes R, Tilling K, Heron J. *J Clin Epidemiol.* 2019;110:63–73. doi:10.1016/j.jclinepi.2019.02.016

## Acceptable limitations
A question card may accept only the Conditional rules the policy lists (for example CMP-004, TIME-002,
SUB-002, CONS-001). An accepted finding stays visible and marked as accepted, no longer lowers the
verdict, and makes human review **required**; approval then needs a written reason. Blocked and
Insufficient Evidence findings can never be accepted, and an attempt to accept one is reported.

## Evidence behind each finding
Every finding carries the columns of the event's findings template: check performed, fields used,
rows or groups affected, what was found, effect on the intended use, materiality, confidence,
evidence or source (measured value and rule), limitation, recommended next step, and whether a person
must review. It also states **what would change the verdict**. Findings download as that template CSV.

**Uncertainty:** each measured rate shows a 95% Wilson range. If the range crosses the rule's threshold,
the finding is marked **borderline**. Counts that are exact say so.

**Which samples can answer it:** records remaining after each group condition and each required
field, and a CSV of every record with whether it can answer the question and where it dropped out.

## Patient-data model
`patient_derived` (true for real, even de-identified, data such as TCGA), `identifiable` (must be false)
and `access` (open only). De-identified open-access patient data is allowed; identifiable or
controlled-access data is Blocked; an undeclared status is Insufficient Evidence.

## Review step
| Verdict | Decisions available |
|---|---|
| Ready | Approve, reject, ask for more evidence |
| Conditional | Approve with conditions, reject, ask for more evidence |
| Blocked, Insufficient Evidence | Reject, ask for more evidence |

Approval requires acknowledging every finding; any decision other than a clean approval requires a
note. The verdict being reviewed is read from the signed certificate, never from the browser. The
review itself is signed (Ed25519) and saved with the evidence record.

## Threat model
| Risk | Mitigation |
|---|---|
| Text hidden in the data steering an AI | Data text never reaches a model raw; flagged text is reported by location only; rules, not models, set verdicts |
| Generated wording contradicting the verdict | Report text that omits or changes the verdict, or drops a Blocked rule, is replaced by a template |
| A clinical question mislabelled as research | A wording guard (SCOPE-002) backs up the intended-use field |
| Results edited after the fact | Certificates bind data checksums, question, rule version and verdicts; edits fail verification |
| A review attached to a forged result | Reviews are accepted only for results whose certificate verifies |
| History rewritten later (a verdict or decision quietly changed or deleted) | Hash-chained, signed audit ledger; `python -m cohort_firewall.ledger verify` names the first broken entry |
| Arbitrary paths from the browser | The API only opens release folders it lists itself; envelope input is validated and passed without a shell |
| Data retention | Uploads are evaluated in memory; stored records hold checksums and results |
