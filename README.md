# Cohort Firewall

**Is this oncology dataset ready for this AI question, and is a new release still safe to use?**

Cohort Firewall checks TCGA-BRCA data before anyone trains on it or reruns an analysis. It returns one
of four verdicts, **Ready**, **Conditional**, **Blocked** or **Insufficient Evidence**, and shows the
evidence, the rule and the fix behind every one.

> **Research tool only.** No diagnosis, treatment recommendation or patient risk score, and no claim
> of clinical validity, regulatory compliance or production readiness.

| | |
|---|---|
| **Event** | OncoSys AI Healthcare Hackathon at Northeastern, Nov 11–14, 2026 |
| **Result** | **Second place, Track 1 (Best Cohort Firewall)** |
| **Track** | Cohort Firewall |
| **Product** | Cohort Control Tower (featured), extended with question-readiness verdicts |
| **Team** | Ninad Rao, Kareesa Rao, Sreelasya Changalasetty, Sanica Chaudhary |
| **Product output** | `findings.json` in shared format v0.2. Example: [`examples/outputs/findings-practice-B.json`](examples/outputs/findings-practice-B.json) |
| **Demo video** | [Edited walkthrough (3 min)](https://youtu.be/HmnjMwQLBB8) · [Code-freeze submission](https://youtu.be/6q2zScy7b7Y) |
| **Live demo** | [cohort-firewall.vercel.app](https://cohort-firewall.vercel.app) (synthetic data with made-up IDs; real TCGA runs stay local) |

## Contents
- [Who it's for](#who-its-for)
- [What it does](#what-it-does)
- [Results](#results)
- [Quick start](#quick-start)
- [Using it](#using-it)
- [How it decides](#how-it-decides)
- [Limitations](#limitations)
- [Tests](#tests)
- [Data and privacy](#data-and-privacy)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)

## Who it's for
A **research engineer** who looks after the TCGA-BRCA dataset. When a new release arrives, they need
to know what changed, which protected analyses it breaks, and whether the data can still answer the
research questions people want to ask, before anyone relies on it.

## What it does

### Release check (Cohort Control Tower)
Compare a new release with the event's frozen release.

1. **Finds what changed, without being told what to look for:** swapped samples, profiles copied onto
   other IDs, samples added or removed, a sample count that stayed the same while membership changed,
   changed clinical labels, new samples with no clinical record, and coverage lost per ER status and
   PAM50 subtype. It also tests whether the changes cluster at one tissue source site.
2. **Maps each change to the analyses it affects.** Affected analyses are rerun with before and after
   values. Unaffected analyses are **not rerun**, and the tool says why.
3. **Gives each analysis a verdict** with the rule, the evidence and the fix.
4. **Hands off a `findings.json`** in the event's shared format v0.2, with proposed repairs, ready for a
   Repair Review Desk.

**Why it matters, not just what changed.** For each affected analysis the tool reports how far it
moved compared with sampling noise (a bootstrap of the organizers' own code), simulates the proposed
repairs to show the analysis returning to baseline and which problem accounts for how much of the
shift, and tests whether losses concentrated in one subtype could be chance. See
[`docs/CONTROL_TOWER.md`](docs/CONTROL_TOWER.md#why-it-matters-size-repairs-and-chance).

### Question check (readiness)
Describe a research question as a set of filters: intended use, who is studied, outcome, predictors,
fairness attributes and acceptable limitations. The verdict changes when the question changes.

- Shows **which samples can answer it**, step by step, with a downloadable sample list.
- Checks missing values, unlikely values, inconsistent records, unclear fields, bias across subgroups,
  unfair shortcuts (leakage), short follow-up, patients counted twice, identifiers and missing source details.
- Gives every finding an **evidence record**: check, fields, rows affected, measured value with a 95%
  range, decision rule, limitation, next step, and what would change the verdict.

### Human review, on both screens
A reviewer records **approve**, **approve with conditions**, **reject** or **ask for more evidence**.
Every decision needs a named reviewer and a written note, Ready included. Blocked and Insufficient
Evidence results can't be approved, and conditional approval also needs every finding acknowledged.
The review is signed, timestamped and saved with the evidence record.

## Results

| Test | Outcome |
|---|---|
| Practice release B (public answer key) | **11 / 11** changes found, 0 unexplained findings |
| Three private releases built with the event's `make_release.py --config` | **22 / 22** changes found, 0 unexplained findings |
| Practice sealed envelope (Saturday's format, no RNA) | **11 / 11**, about 7 s after unsealing |
| Fresh clone on a clean folder | Setup, tests, a real comparison, the validator and the web build all pass |
| **Independent rerun by the organizers** (clean computer, README only; applies to the code-freeze version [v0.1.0](../../tree/ab5084f), commit `ab5084f`) | One-command setup in 45 s; all 64 test checks passed; 4 / 4 planted changes found on an unseen release, no false alarms; the unaffected analysis correctly left alone. The web app wasn't part of their run |

On the frozen release, the same data gets different verdicts for different questions:

| Question | Verdict | Why |
|---|---|---|
| ER-alpha protein vs clinical ER status | Conditional | 33% of eligible tumors have no protein data |
| Same, protein-profiled tumors only | Ready | 698 tumors with complete data |
| 5-year overall survival | Conditional | Only 32% followed for 5 years (median 27.7 months) |
| PAM50 subtype mix | Conditional | The two PAM50 calls disagree for 52 of 508 tumors (10%) |
| 2-year progression, fairness across race | Insufficient Evidence | The release doesn't record race |
| A patient-level risk score | Blocked | Out of scope by the event rules |

Details: [`docs/RESULTS.md`](docs/RESULTS.md).

## Quick start
Requires Python 3.10+, git, and Node.js for the web app. Tested with Python 3.13.12 and Node.js v26.13.0 on macOS.

```bash
git clone https://github.com/NinadRao0707/cohort-firewall.git
cd cohort-firewall
bash scripts/setup.sh
bash scripts/run.sh
```

Then open **http://localhost:3000/tower** (Release check) or **http://localhost:3000** (Question check).

**Windows:** run the two scripts from WSL or Git Bash. Without them, follow the steps in `scripts/setup.sh`
by hand: `py -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements.txt`, then the commands it lists.

`setup.sh` creates the Python environment (installing the exact versions in `requirements.lock` when present), clones the event's challenge repository next to this one
(or uses `$CF_CHALLENGE_REPO`), fetches the frozen TCGA-BRCA files and verifies their checksums,
builds practice release B, builds the readiness table, signs the saved samples with a key generated
on your machine, runs the test suites and installs the web app. It's safe to run again. `run.sh`
starts the API and the web app together; press Ctrl+C to stop both.

<details>
<summary>Command line only, without Node.js</summary>

```bash
source .venv/bin/activate
python -m cohort_firewall.tower \
  --challenge-repo ../oncosys-hackathon-challenge \
  --b ../oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B \
  --out outputs/findings-practice-B.json
python ../oncosys-hackathon-challenge/format/validate.py outputs/findings-practice-B.json
python scripts/run_tcga_specs.py
```
</details>

<details>
<summary>macOS: <code>CERTIFICATE_VERIFY_FAILED</code> when fetching data</summary>

`setup.sh` already sets `SSL_CERT_FILE` from `certifi`. If you run `fetch.py` yourself, run
`export SSL_CERT_FILE="$(python -m certifi)"` first.
</details>

## Using it

### Compare a new release
| Where the release is | What to do |
|---|---|
| A sealed envelope from a judge | Release check → **+ Open envelope** → number and four-word code → **Open and compare** |
| Any folder | `python -m cohort_firewall.tower --b <folder> --out outputs/findings.json` |
| A `make_release.py` config | Release check → **More** → **Build a release from a make_release config** |
| A folder under `data/tcga-brca/releases/` | Pick it in the **Release** chip, then **Compare releases** |

Releases that leave out a file (envelopes have no RNA) are handled: missing files are listed as
"not compared", never reported as changes. See [`docs/HIDDEN_TEST.md`](docs/HIDDEN_TEST.md).

### Check a research question
On Question check, write the question in one sentence, or open **Examples**. Set the filter chips
(**Use**, **Who**, **Outcome**, **Predictors**, **Fairness**, **Accepts**), then select **Check readiness**.
Results open with the verdict and a plain-English summary; the tabs hold next steps, findings,
samples, all checks and the review.

## How it decides
- **Checks measure; rules decide.** Every verdict comes from a versioned rule file you can read:
  [`rules/tower_v0_1.yaml`](rules/tower_v0_1.yaml) for releases and
  [`rules/policy_v0_1.yaml`](rules/policy_v0_1.yaml) for questions.
- **Worst finding wins:** Blocked > Insufficient Evidence > Conditional > Ready.
- **Nothing passes by default.** Anything the tool can't verify, including a baseline that doesn't
  match the event's frozen checksums, is Insufficient Evidence.
- **Question-specific.** A problem in a field the question doesn't use is noted, not counted.
- **Acceptable limitations** from the question card can only cover Conditional findings. They stay
  visible, and approval then needs a written reason.
- **Signed records.** Every result carries an Ed25519 certificate binding the data checksums, the
  question and the rule version. An edited result or review fails verification.

Details: [`docs/DESIGN.md`](docs/DESIGN.md) and [`docs/CONTROL_TOWER.md`](docs/CONTROL_TOWER.md).

## Security by design
Built by cybersecurity students, it treats every data release the way a security team treats a software
release: nothing is trusted until it's verified, and every decision leaves evidence.

| Control | What it does |
|---|---|
| **Verified provenance** | The baseline must match the event's published checksums, or every verdict is Insufficient Evidence |
| **Default deny** | Anything the tool can't verify fails closed; nothing passes by default |
| **Reproducible installs** | `requirements.lock` pins the exact package versions that produced the signed results |
| **Signed results** | Each result carries an Ed25519 certificate binding the data checksums, the question, the rules and the verdicts |
| **Signed, evidence-bound reviews** | A review attaches only to a result whose signature verifies; if the evidence changes, the certificate changes and a fresh review is needed |
| **Tamper-evident audit ledger** | Every check, envelope opening and review is a signed entry chained to the one before it (like a Certificate Transparency log). Editing, deleting or reordering any past entry breaks the chain at that entry |
| **Injection-safe** | Text inside the data can never steer a verdict; instruction-like text is reported by location only |
| **Identifier screening** | Identifier-like fields and values block the data |
| **Small-cell suppression** | The shareable summary hides counts from 1 to 10 (CMS rule); the evidence record keeps exact counts for reviewers |
| **Least privilege** | The API opens only release folders it lists itself; envelope input is validated and run without a shell |
| **No secrets in the repo** | Keys are generated locally and git-ignored; history scanned with Gitleaks |

```bash
python -m cohort_firewall.ledger verify   # "Ledger intact: N entries, head …"
python -m cohort_firewall.ledger show     # the latest entries
python scripts/tamper_demo.py             # change a past verdict in a copy, and watch verify catch it
```
In the app: **Record** (Release check) or **Review** (Question check) → **Verify the ledger**.

**Limitation:** removing entries from the very end leaves a shorter valid chain. Record the head hash
elsewhere (a review note, a ticket) to detect that, as transparency logs do.

## Since the hackathon
After judging, the organizers shared written feedback with six suggestions. All six are implemented:
review on every verdict, confidence that follows the evidence, summaries kept apart from findings,
probable-swap detection for swaps hidden by value edits, a one-sentence release headline with "what
would change the verdict" on every next step, and pinned dependency versions. The web app also has a
public demo mode that uses synthetic data only. See [`CHANGELOG.md`](CHANGELOG.md).

## Limitations
These are also shown in the product, under **Limitations of this check**, and on every finding.

- Change detection compares exact values. A swap with small edits on top is caught by a near-match pass
  and reported as a *probable* swap with medium confidence; other edits hidden inside a copied profile show as value edits.
- The tool shows *what* changed, not which release is correct. Every repair needs a person's decision.
- Identifier detection is pattern-based; a pass doesn't prove no personal information is present.
- Leakage detection checks one field at a time.
- Thresholds (10 events per parameter, 50 records per subgroup, 20% and 50% missingness) are
  configurable defaults, not clinical standards.

## Tests
```bash
source .venv/bin/activate
python tests/test_tower.py                                    # 13 release scenarios, incl. no RNA, shared-profile copies, near-match swaps
python data/make_variants.py && python tests/test_variants.py # 26 seeded-defect readiness cases
python tests/test_review.py                                   # 14 review rules: approval limits, notes on every verdict, forged results
python tests/test_ledger.py                                   # audit ledger: edits, deletions, reordering, forgeries
python tests/test_disclosure.py                               # small-cell suppression keeps IDs, hides counts 1-10
python tests/test_public_demo.py                              # the hosted demo can only ship synthetic samples
bash scripts/rehearse.sh                                      # 3 private releases, graded against their answer keys
bash scripts/fresh_clone_test.sh                              # what a judge does, from an empty folder
```

## Data and privacy
- **Judged results** use the event's frozen TCGA-BRCA release, fetched by the challenge repository's
  `fetch.py` and verified against its `sources.csv`. The data is de-identified but patient-derived:
  research use only, no re-identification.
- **No raw TCGA files are in this repository.** `data/tcga/` and `outputs/` are git-ignored. Small
  derived outputs (`examples/outputs/`, `web/public/samples/`) hold sample barcodes and summary numbers only.
- **Synthetic data, for engine tests only:** a generated stand-in cohort (`data/make_demo_cohort.py`)
  and optional Synthea output. Neither contains real patients, and neither is used for judged results.
- **The hosted browser demo uses synthetic data only**, with made-up `DEMO-` IDs and random values.
  Saved results with real TCGA sample IDs are removed at build time and never deployed; real TCGA
  runs happen locally. `tests/test_public_demo.py` checks this.
- **No keys or secrets are committed.** The signing key is generated locally in `keys/` (git-ignored).

### AI features
Nothing in the tool needs a language model. An optional parser can turn a plain-English question into
filters using a key the user supplies (`ANTHROPIC_API_KEY`); the model never decides a verdict, and
report text that changes the verdict is rejected.

## Repository layout
| Path | Contents |
|---|---|
| `cohort_firewall/tower/` | Release comparison: loading, change detection, analysis impact, `findings.json` |
| `cohort_firewall/` | Readiness engine: question spec, checks, rules, evidence, review, certificates |
| `rules/` | The two versioned rule files |
| `api/main.py` | FastAPI service used by the web app |
| `web/` | Next.js web app: Release check and Question check |
| `data/` | TCGA readiness table builder and synthetic test data generators |
| `scripts/` | Setup, run, grading, rehearsal and export scripts |
| `examples/` | Example question cards and a saved practice-B `findings.json` |
| `rehearsal/` | Private release configs used for rehearsal |
| `tests/` | Release, readiness and review tests |
| `docs/` | Design, results, demo and runbook documents |

## Documentation
| Document | What it covers |
|---|---|
| [`docs/RESULTS.md`](docs/RESULTS.md) | Every result, with how to reproduce it |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Verdicts, checks, rules, evidence, review and threat model |
| [`docs/CONTROL_TOWER.md`](docs/CONTROL_TOWER.md) | How release comparison works |
| [`docs/HIDDEN_TEST.md`](docs/HIDDEN_TEST.md) | Opening a sealed envelope and running the tool live |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | The 3-minute demo and likely questions |
| [`docs/USER_TEST.md`](docs/USER_TEST.md) | A 5-minute test of whether users reach the right conclusions |
| [`docs/SYNTHEA_SETUP.md`](docs/SYNTHEA_SETUP.md) | Optional synthetic data for engine testing |
| [`web/README.md`](web/README.md) | Working on the web app |
| [`rehearsal/README.md`](rehearsal/README.md) | The private rehearsal releases |
| [`THIRD_PARTY.md`](THIRD_PARTY.md) | Third-party code, data and licenses |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed since the code-freeze submission |
