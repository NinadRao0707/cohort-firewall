# Cohort Firewall

Decides whether an oncology dataset is ready for a **specific** proposed AI question:
**Ready**, **Conditional**, **Blocked**, or **Insufficient Evidence**.

Built for the OncoSys AI / The Open Accelerator AI Healthcare Hackathon at Northeastern (Cohort Firewall track).

## Core idea

Readiness is a property of a dataset *and* a question together. The same cohort can be Ready
for 2-year recurrence modeling, Conditional for 5-year survival (follow-up too short), and
Blocked for a treatment recommendation (out of scope).

```
CSV + data dictionary ─┐
question ── LLM parser ─┴─► QuestionSpec (validated) ─► deterministic checks (pandas)
                                                              │ metrics
                                        rules/policy_v0_1.yaml ─► verdict + findings
                                                              │
                         LLM wording (guarded) or template ◄──┤
                         Ed25519-signed certificate      ◄────┘
```

The LLM parses the question and words the report. **It never decides the verdict.**

## Quickstart (works offline, no API key)

```bash
pip install -r requirements.txt
python data/make_demo_cohort.py      # stand-in Synthea-shaped breast cohort
python data/make_variants.py         # 16 seeded-defect test cases
python tests/test_variants.py        # expected vs actual verdict table
uvicorn api.main:app --reload        # http://localhost:8000/docs
```

Optional: `export ANTHROPIC_API_KEY=...` and pass `use_llm_parser=true` / `use_llm_report=true`.
Optional: `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` to log runs (schema in `supabase/schema.sql`).

## Repo map

| Path | What it is |
|---|---|
| `cohort_firewall/spec.py` | QuestionSpec schema + strict validation |
| `cohort_firewall/checks.py` | 12 deterministic checks, each returns metrics only |
| `rules/policy_v0_1.yaml` | Policy-as-code: metrics → verdict, thresholds, reasons, remedies |
| `cohort_firewall/policy.py` | Rule evaluator, precedence, default-deny |
| `cohort_firewall/certificate.py` | Signed readiness certificate + verify |
| `cohort_firewall/llm.py` | Question parser and report wording (Claude API) |
| `cohort_firewall/report.py` | Template report + guard that rejects LLM text that alters the verdict |
| `api/main.py` | FastAPI: `/evaluate`, `/verify`, `/public-key`, `/policy` |
| `data/flatten_synthea.py` | Synthea CSV export → one patient-level cohort table + dictionary |
| `data/make_variants.py` | Seeded-defect cases (the evaluation) |
| `examples/specs/` | Four questions against the same cohort |
| `web/` | Next.js UI (runs on sample results without the API) |
| `scripts/smoke_api.sh` | First real test of the API endpoints |
| `scripts/try_parser.py` | Trial of the Claude question parser on 5 questions |
| `scripts/create_github_issues.sh` | Creates the pre-kickoff task list as GitHub issues |
| `docs/` | Design, kickoff questions, demo script, Synthea setup, pre-kickoff plan |

## Status (pre-kickoff)

Tested offline: spec validation, all checks, policy engine, certificates, template reports,
16-case suite, Synthea flattener on a fixture, and the web UI's result views (server-rendered
and screenshotted in light, dark and phone widths).

Written but not yet run: FastAPI layer (`scripts/smoke_api.sh` tests it), Claude API calls
(`scripts/try_parser.py`), Supabase logging, and a full `next build` of the web app.
