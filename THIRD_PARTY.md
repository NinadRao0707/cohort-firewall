# Third-party code, data and licenses

Licenses as published by each project; check the installed version's metadata
(`pip show <package>`, `npm view <package> license`) if in doubt.

## Python packages (requirements.txt)
| Package | Use | License |
|---|---|---|
| pandas | data loading and checks | BSD-3-Clause |
| NumPy | numerics | BSD-3-Clause |
| PyYAML | policy files | MIT |
| cryptography | Ed25519 certificate signing | Apache-2.0 OR BSD-3-Clause |
| FastAPI | API | MIT |
| Uvicorn | API server | BSD-3-Clause |
| Pydantic | request validation | MIT |
| python-multipart | file uploads | Apache-2.0 |
| anthropic (optional) | plain-English question parsing | MIT |
| supabase (optional) | run log | MIT |
| jsonschema (via the challenge repo's validator) | findings.json validation | MIT |

## JavaScript (web/)
| Package | License |
|---|---|
| Next.js | MIT |
| React, React DOM | MIT |
| TypeScript | Apache-2.0 |

## Fonts
Public Sans and Source Serif 4, loaded through `next/font/google`: SIL Open Font License 1.1.

## Event materials used at runtime (not copied into this repository)
- The challenge repository's `data/tcga-brca/reference_analyses.py`, `make_release.py`, `fetch.py`,
  `sources.csv`, manifests and `format/` validator are read from a local clone of
  https://github.com/disleveK/oncosys-hackathon-challenge. See its `DATA_LICENSES.md`.
- TCGA-BRCA data: TCGA open access via the UCSC Xena TCGA hub; survival from the TCGA Pan-Cancer
  Clinical Data Resource (Liu et al., Cell 2018). Credit the TCGA Research Network. Not
  redistributed here.

## Test data
- Synthea (optional, engine testing only): Apache-2.0, MITRE. Generated output is not committed.
