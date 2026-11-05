#!/usr/bin/env bash
# Creates the pre-kickoff task list as GitHub issues. Needs the GitHub CLI: gh auth login
# Run from inside the repo folder:  bash scripts/create_github_issues.sh
set -euo pipefail
gh label create backend  --color 1f6feb --force >/dev/null
gh label create frontend --color 8957e5 --force >/dev/null
gh label create data     --color 1a7f37 --force >/dev/null
gh label create pitch    --color bf8700 --force >/dev/null

issue() { gh issue create --title "$1" --label "$2" --body "$3" >/dev/null && echo "created: $1"; }

issue "Run API smoke tests" backend \
"Start \`uvicorn api.main:app --reload\`, then run \`bash scripts/smoke_api.sh\`. All lines should say PASS. Paste any failure into the team chat."
issue "Test the Claude question parser" backend \
"Set ANTHROPIC_API_KEY and run \`python scripts/try_parser.py\`. Record which of the 5 questions get the expected verdict. Tune PARSER_SYSTEM in cohort_firewall/llm.py if needed."
issue "Connect Supabase run log" backend \
"Create a Supabase project, run supabase/schema.sql in the SQL editor, set SUPABASE_URL and SUPABASE_SERVICE_KEY, \`pip install supabase\`, and confirm a row appears after /evaluate."
issue "Run the web app against sample results" frontend \
"Follow web/README.md. Open each sample result, check light/dark mode and a phone-width window. List anything that looks wrong."
issue "Connect the web app to the API" frontend \
"Set NEXT_PUBLIC_API_URL in web/.env.local, upload data/variants/clean files with the spec, confirm the verdict and Verify signature work."
issue "Generate Synthea breast cancer data" data \
"Follow docs/SYNTHEA_SETUP.md through the --inspect step and share the printed descriptions."
issue "Map Synthea fields and run the firewall on real Synthea output" data \
"Fill FEATURE_KEYWORDS in data/flatten_synthea.py from the inspect output, flatten, and evaluate with a death-outcome question."
issue "Draft the 3-minute pitch" pitch \
"Start from docs/DEMO_SCRIPT.md. Update once the kickoff gives the demo length and judging criteria."
issue "Prepare kickoff questions" pitch \
"Review docs/KICKOFF_QUESTIONS.md, add your own, and bring it to the Nov 11 virtual kickoff."
