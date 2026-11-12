# Live test runbook

At the start of the Q&A a judge gives you an **envelope number** and a **four-word code**. The envelope
holds a new TCGA-BRCA release: five files, no RNA and no answer key. Unsealing takes about 15 seconds.

## In the web app (one screen)
1. **Release check** → **+ Open envelope**.
2. Type the number (`07`) and the code (`amber falcon river quartz`) → **Open and compare**.
3. Read **In plain terms** aloud, then each analysis's verdict, then the first **Next step**.
4. **Record** → **Download findings.json**: the file the organizers' checker reads.

## In the terminal (fallback)
```bash
cd ~/oncosys-hackathon-challenge
python envelopes/unseal.py 07 amber falcon river quartz

cd ~/cohort-firewall && source .venv/bin/activate
python -m cohort_firewall.tower \
  --b ~/oncosys-hackathon-challenge/envelopes/opened/E07/release \
  --out outputs/findings-E07.json
python ~/oncosys-hackathon-challenge/format/validate.py outputs/findings-E07.json
```

## Rehearse with the practice envelope
The practice code is public. The practice envelope is practice-B without RNA, so it should grade 11 / 11.
```bash
cd ~/oncosys-hackathon-challenge
python envelopes/unseal.py practice orange meadow pilot lantern

cd ~/cohort-firewall
python -m cohort_firewall.tower \
  --b ~/oncosys-hackathon-challenge/envelopes/opened/practice/release \
  --out outputs/findings-envelope-practice.json
python scripts/grade_tower.py outputs/findings-envelope-practice.json \
  ~/oncosys-hackathon-challenge/data/tcga-brca/releases/practice-B/CHANGES.json
```

## If a judge changes the research question instead
On **Question check**, set the chips to match what they say (**Use**, **Who**, **Outcome**,
**Predictors**, **Fairness**, **Accepts**) and select **Check readiness**. Change one chip at a time
and say what moved and why.

## Troubleshooting
| Message | Fix |
|---|---|
| "That code doesn't open envelope…" | Check the number and the four words; spaces or hyphens and any capitals work |
| "Release A isn't here" or a fingerprint error | Run `python data/tcga-brca/fetch.py` in the challenge repository (do this before Saturday) |
| An error in the web page | Check `outputs/api.log`, restart with `bash scripts/run.sh`, or use the terminal fallback |
