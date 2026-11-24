# Web app

The Next.js reviewer interface for Cohort Firewall: **Release check** (`/tower`) and **Question check** (`/`).

## Run
The simplest way is from the repository root, which starts the API too:
```bash
bash scripts/run.sh
```

To work on the web app alone:
```bash
cd web
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Without `NEXT_PUBLIC_API_URL`, the app runs in **saved-results mode**: it opens the results in
`public/samples/` but can't run live checks. Regenerate those samples, signed with your local key,
with `python scripts/export_web_samples.py`.

## Build
```bash
npm run build
```

## Layout
| Path | Contents |
|---|---|
| `app/page.tsx` | Question check |
| `app/tower/page.tsx` | Release check, including Open envelope |
| `components/QuestionCard.tsx` | The question filter bar |
| `components/Popover.tsx` | Filter chips, popovers and phone bottom sheets |
| `components/Results.tsx`, `TowerResults.tsx` | Verdict header and result tabs |
| `components/Findings.tsx`, `Funnel.tsx`, `ChecksTable.tsx` | Findings, samples and checks |
| `components/ReviewPanel.tsx`, `CertificatePanel.tsx` | Human review and signed records |
| `lib/` | API clients and response types |
| `public/samples/` | Saved results for offline use |

## Deploying the public demo (Vercel)
Live at **https://cohort-firewall.vercel.app**. The hosted site is a **synthetic-data demo**. On Vercel, demo mode turns on automatically:
- a banner says the data is synthetic, and only synthetic examples are listed;
- Release check opens a synthetic run (`public/samples/tower_demo.json`, made by
  `python scripts/build_public_demo.py`) with made-up `DEMO-` IDs and random values;
- before building, `scripts/prepare-demo.mjs` **deletes every saved sample that isn't on the synthetic
  allow-list**, so results with real TCGA sample IDs are never deployed, not even by direct URL.

Real TCGA-BRCA runs stay local. Live checks need the API and the frozen data, so they also run locally.

Setup: import the repo on Vercel, set **Root Directory** to `web`, and deploy. `vercel.json` already
sets the build command. Leave `NEXT_PUBLIC_API_URL` unset. To preview demo mode locally:
`NEXT_PUBLIC_DEMO_MODE=1 npm run dev`.
