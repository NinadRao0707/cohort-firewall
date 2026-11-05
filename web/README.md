# Cohort Firewall web app (Next.js)

## First run (sample results only, no API needed)
```bash
cd web
npm install next@latest react@latest react-dom@latest
npm install -D typescript @types/react @types/react-dom @types/node
npm run dev
```
Open http://localhost:3000 and click any sample result in the left column.
If `next dev` prompts to adjust tsconfig.json or creates next-env.d.ts, accept it.

## Connect to the API
```bash
cp .env.local.example .env.local      # sets NEXT_PUBLIC_API_URL=http://localhost:8000
```
Restart `npm run dev`. With the API running (`uvicorn api.main:app --reload` from the repo root),
upload `data/variants/clean/data.csv` and `dictionary.json`, choose "Question spec (JSON)",
paste `spec.json`, and click Check readiness. Expected verdict: Ready.

## Structure
- `app/page.tsx` page state and data flow
- `components/VerdictGate.tsx` the four-step verdict scale (the one bold element)
- `components/Findings.tsx`, `ChecksTable.tsx`, `CertificatePanel.tsx`
- `lib/types.ts` response types mirroring `/evaluate`; `lib/api.ts` API client and sample list
- `public/samples/*.json` real engine output used for offline development

Not yet built or tested with `next build` (written offline). Report any type errors and they'll be fixed.
