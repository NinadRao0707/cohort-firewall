# Third-party code, data and licenses

Licenses are as published by each project. Check an installed version with `pip show <package>` or
`npm view <package> license`.

## Python
Installed by `requirements.txt`:

| Package | Used for | License |
|---|---|---|
| pandas | Data loading and checks | BSD-3-Clause |
| NumPy | Numerics | BSD-3-Clause |
| PyYAML | Rule files | MIT |
| cryptography | Ed25519 signing of results and reviews | Apache-2.0 or BSD-3-Clause |
| FastAPI | API | MIT |
| Uvicorn | API server | BSD-3-Clause |
| Pydantic | Request validation | MIT |
| python-multipart | File uploads | Apache-2.0 |
| certifi | TLS certificates for data downloads | MPL-2.0 |
| jsonschema | Validating `findings.json` with the event's validator | MIT |

Optional, in `requirements-optional.txt`:

| Package | Used for | License |
|---|---|---|
| anthropic | Plain-English question parsing (user supplies the key) | MIT |
| supabase | Optional run log | MIT |
| pytest | Running the tests with pytest | MIT |

## JavaScript (`web/`)
| Package | License |
|---|---|
| Next.js | MIT |
| React, React DOM | MIT |
| TypeScript | Apache-2.0 |

## Fonts
Public Sans and Source Serif 4, loaded through `next/font/google`: SIL Open Font License 1.1.

## Event materials (used at run time, not copied here)
From a local clone of https://github.com/disleveK/oncosys-hackathon-challenge: `reference_analyses.py`,
`make_release.py`, `fetch.py`, `sources.csv`, the manifests, `envelopes/unseal.py` and the `format/`
validator. See that repository's `DATA_LICENSES.md`.

## Data
- **TCGA-BRCA:** TCGA open access, via the UCSC Xena TCGA hub; survival data from the TCGA Pan-Cancer
  Clinical Data Resource (Liu et al., *Cell*, 2018). Credit: the TCGA Research Network. Not redistributed here.
- **Synthea** (optional, engine testing only): Apache-2.0, MITRE. Generated output is not committed.
