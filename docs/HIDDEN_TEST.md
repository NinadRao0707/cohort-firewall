# Hidden test runbook (the 2 minutes of questions)

At the start of your Q&A a judge gives you an **envelope number** and a **four-word code**. The
envelope holds a new TCGA-BRCA release (5 files, no RNA, no answer key).

## Fastest: in the web app (one screen)
1. Release check, then **+ Open envelope**.
2. Type the number (e.g. `07`) and the code (e.g. `amber falcon river quartz`), then **Open and compare**.
3. About 15 s to unseal, then the comparison. Read **In plain terms** aloud, then each analysis's
   verdict, then Next steps 1.
4. Record tab, then **Download findings.json**, the file the organizers' checker reads.

## Fallback: terminal
```bash
cd ~/oncosys-hackathon-challenge
python envelopes/unseal.py 07 amber falcon river quartz
cd ~/cohort-firewall && source .venv/bin/activate
python -m cohort_firewall.tower --b ~/oncosys-hackathon-challenge/envelopes/opened/E07/release --out outputs/findings-E07.json
python ~/oncosys-hackathon-challenge/format/validate.py outputs/findings-E07.json
```

## Rehearse (practice envelope, public code)
```bash
cd ~/oncosys-hackathon-challenge && python envelopes/unseal.py practice orange meadow pilot lantern
cd ~/cohort-firewall && python -m cohort_firewall.tower --b ~/oncosys-hackathon-challenge/envelopes/opened/practice/release --out outputs/findings-envelope-practice.json
python scripts/grade_tower.py outputs/findings-envelope-practice.json ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B/CHANGES.json
```
The practice envelope is practice-B without RNA, so it should grade 11/11.

## If something goes wrong
- "That code doesn't open envelope…": check the number and the four words (spaces or hyphens, any case).
- "Release A isn't here" or a fingerprint error: `python data/tcga-brca/fetch.py` (do it before Saturday).
- API error in the page: see `outputs/api.log`; restart with `bash scripts/run.sh`, or use the terminal fallback.
