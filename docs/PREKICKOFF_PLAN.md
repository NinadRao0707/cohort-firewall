# Pre-kickoff plan (Nov 5 to Nov 11)

Track each item as a GitHub issue (`bash scripts/create_github_issues.sh` creates them).

| Day | Task | Owner | Done when |
|---|---|---|---|
| Nov 5–6 | Repo set up, teammates added | | Everyone can clone and push a branch |
| Nov 6 | Engine tests pass on every laptop | all | `python tests/test_variants.py` all PASS |
| Nov 6 | API smoke tests | backend | `bash scripts/smoke_api.sh` all PASS |
| Nov 6–7 | Web app runs on sample results | frontend | All 8 samples render, light and dark |
| Nov 7 | Synthea generated and inspected | data | Inspect output shared |
| Nov 7–8 | Claude parser trial | backend | 5 trial questions give expected verdicts |
| Nov 8 | Web app connected to API | frontend | Upload, verdict and Verify signature work |
| Nov 8–9 | Synthea mapped and evaluated | data | Firewall runs on real Synthea cohort |
| Nov 9 | Supabase run log | backend | Rows appear after each evaluation |
| Nov 10 | Dry-run the demo script end to end | all | Under the time limit, no manual fixes |
| Nov 11 | Kickoff: ask docs/KICKOFF_QUESTIONS.md | all | Answers written into this repo |

If the kickoff says code must be written during the build days, keep this repo as research and
design notes and rebuild from it on Nov 12; the decisions and tests carry over.
