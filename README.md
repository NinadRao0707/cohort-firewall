# Cohort Firewall: Cohort Control Tower with readiness verdicts

**Track:** Cohort Firewall · **Product:** Cohort Control Tower (featured), extended with readiness verdicts
**Team:** _FILL IN: names of all 3-5 members_
**Demo video:** _FILL IN: link_

> Research data-quality and data-readiness tool. Not a clinical tool: no diagnosis, treatment
> recommendation, or patient risk score, and no claim of clinical validity, regulatory compliance,
> or production readiness.

## The user and the one workflow
**User:** a research engineer responsible for the TCGA-BRCA dataset, which gets new releases.

**Workflow they finish:** a new release arrives. They open **Release check**, pick the release and
compare it with the event's frozen release. The tool shows:
1. what changed, found without being told what to look for: swapped samples, profiles copied
   onto other IDs, samples removed or added, a sample count that stayed the same while membership
   changed, clinical labels that changed, and genuine coverage lost per ER status and PAM50 subtype;
2. which protected analyses each change affects **and which it doesn't**; affected analyses are
   rerun with before/after results, unaffected ones are **not rerun** and the tool says why;
3. a verdict per analysis (Ready / Conditional / Blocked / Insufficient Evidence) with the rule,
   the evidence and the fix, and where a person must review before use;
4. proposed repairs and a `findings.json` (shared format v0.2) to hand to a Repair Review Desk.

The same verdict engine also answers **Question check**: is the frozen release fit for a specific
research question? A judge fills in a **research-question card** (intended use, group studied,
outcome, predictors, subgroups, acceptable limitations) with no code or API key, and the verdict
changes when the card changes. For example, a fairness check across race is Insufficient Evidence
because the release doesn't record race.

Every finding carries its evidence record: the check performed, the data fields and rows used,
the measured value and the decision rule, how it affects this question, materiality, confidence,
the check's limitation, the next step and the evidence that would change the verdict. Findings
download as the event's `findings_template.csv` columns. Checks cover missing values, unlikely
values, inconsistent records (two sources for the same fact), unclear fields, bias across
subgroups, unfair shortcuts (leakage) and missing source details.

Both screens end with a **review step**: a person records approve / approve with conditions /
reject / ask for more evidence, after confirming they reviewed each finding. Blocked and
Insufficient Evidence results can't be approved. The review is signed and saved with the evidence
record, and it can only attach to a result whose certificate verifies.

## One result a judge can verify
On the public practice release, the tool reports exactly the answer key's changes, with no
unexplained findings. To reproduce, run steps 1-3 below and then:
```bash
python scripts/grade_tower.py outputs/findings-practice-B.json ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B/CHANGES.json
```
Every finding lists the sample barcodes and file it rests on; every analysis shows its before and
after values, computed by the event's own `reference_analyses.py`.

## One limitation a judge can inspect
Shown in the product under **Limitations of this check** and on every finding. The main one:
change detection compares exact values, so a swap or copy that also edits values is reported as
value edits instead. The tool also shows *what* changed, not which release is correct: every
repair needs a person's decision.

## Setup from a fresh clone (macOS or Linux)
Tested with: Python 3.13.12, Node.js v26.13.0 (macOS).

**1. The event's challenge repo, next to this one**
```bash
cd ~
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git
git clone https://github.com/NinadRao0707/cohort-firewall.git cohort-firewall
```

**2. Python environment and the frozen data**
```bash
cd ~/cohort-firewall
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ~/oncosys-hackathon-challenge
python data/tcga-brca/fetch.py
python data/tcga-brca/make_release.py
```
`fetch.py` should print six `ok` lines. If it fails with `CERTIFICATE_VERIFY_FAILED` on macOS
(python.org installer), run `open "/Applications/Python 3.13/Install Certificates.command"` (adjust
the version), or `export SSL_CERT_FILE="$(python -m certifi)"`, and fetch again.

**3. Compare a release (command line)**
```bash
cd ~/cohort-firewall
python -m cohort_firewall.tower --b ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B --out outputs/findings-practice-B.json
python ~/oncosys-hackathon-challenge/format/validate.py outputs/findings-practice-B.json
```
If the challenge repo is elsewhere, add `--challenge-repo <path>` (and set `CF_CHALLENGE_REPO`
for the API). To compare **any new release**, put its folder in
`oncosys-hackathon-challenge/data/tcga-brca/releases/<name>/` (for example with
`make_release.py --config <file>`) or pass its path with `--b`.

**4. The web app (two terminals)**
```bash
cd ~/cohort-firewall && source .venv/bin/activate
python data/make_variants.py
python data/flatten_tcga.py --challenge-repo ~/oncosys-hackathon-challenge
python scripts/export_web_samples.py
uvicorn api.main:app --reload
```
`export_web_samples.py` rebuilds the saved sample results and signs them with a key generated on
your machine (in `keys/`, git-ignored), so **Verify signature** works on a fresh clone.
```bash
cd ~/cohort-firewall/web
npm install
cp .env.local.example .env.local
npm run dev
```
Open http://localhost:3000/tower (Release check) or http://localhost:3000 (Question check).

**5. Question check on the frozen release (command line)**
```bash
python scripts/run_tcga_specs.py
```

## Tests
```bash
python tests/test_tower.py
python data/make_variants.py && python tests/test_variants.py
python tests/test_review.py
bash scripts/rehearse.sh
```
- `test_tower.py`: 10 Control Tower scenarios on synthetic releases (no TCGA data needed).
- `test_variants.py`: 25 seeded-defect readiness cases on a synthetic stand-in cohort.
- `test_review.py`: 13 review-step rules (approval limits, acknowledgements, forged results).
- `rehearse.sh`: builds three private releases with the event's `make_release.py --config`, using
  change types practice-B does not use, runs the Control Tower and grades it.

## How it decides
Checks only measure; a versioned rule file decides (`rules/tower_v0_1.yaml` for releases,
`rules/policy_v0_1.yaml` for questions). Worst finding wins: Blocked > Insufficient Evidence >
Conditional > Ready. Anything the tool cannot verify, including a baseline that doesn't match the
event's frozen checksums, is Insufficient Evidence: nothing passes by default. Every result carries
an Ed25519-signed certificate binding the release checksums, the question and the rule version.
Details: `docs/CONTROL_TOWER.md`, `docs/DESIGN.md`.

## Data
- **Judged results:** the event's frozen TCGA-BRCA release, fetched by the challenge repo's
  `fetch.py` and verified against its `sources.csv`. No raw TCGA files are in this repository;
  `data/tcga/` and `outputs/` are git-ignored. Small derived outputs (`examples/outputs/`,
  `web/public/samples/`) hold sample barcodes and summary numbers only. The data is de-identified
  but patient-derived: research use only, no re-identification.
- **Engine tests only (synthetic, no real patients):** a stand-in cohort generated by
  `data/make_demo_cohort.py`, and optional Synthea output (MITRE's synthetic patient generator).
  _FILL IN if organizers asked: "disclosed to organizers at kickoff on Nov 11."_

## AI features
None are required to run the tool. The Question check can optionally use a language model to turn
a plain-English question into a structured spec and to word the report (`cohort_firewall/llm.py`),
with a key the user supplies (`ANTHROPIC_API_KEY`); no key is in this repository. The model never
decides a verdict, and report text that changes the verdict or drops a Blocked finding is rejected.

## Repository map
| Path | What it is |
|---|---|
| `cohort_firewall/tower/` | Control Tower: release loading, change detection, analysis impact, findings.json |
| `cohort_firewall/` | Readiness engine: question spec, checks, policy evaluator, certificates, report |
| `rules/` | The two versioned policy files |
| `api/main.py` | FastAPI: `/tower/releases`, `/tower/run`, `/evaluate`, `/verify`, `/policy` |
| `web/` | Next.js reviewer screens: Release check and Question check |
| `data/flatten_tcga.py` | Verified, barcode-joined readiness table from the frozen release |
| `scripts/` | Graders, rehearsal runner, sample exporter, TCGA question runner |
| `rehearsal/` | Private release configs for rehearsal |
| `examples/` | Question specs and a saved practice-B findings.json |
| `tests/` | Synthetic-release and seeded-defect tests |
| `docs/` | Design, Control Tower notes, demo script |

## Third-party code and licenses
See `THIRD_PARTY.md`.
