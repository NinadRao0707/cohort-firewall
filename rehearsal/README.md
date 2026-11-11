# Rehearsal releases

Private releases built with the event's own `make_release.py --config`, using change types and files
that practice-B does not use. They exist to check the Control Tower on input it was not tuned for.

| Release | Changes | Expected |
|---|---|---|
| rehearsal-C | ER status relabelled to Negative for 3 tumors; 2 protein swaps between **same-ER** samples | A1 Blocked (swap + ER label); A2 Ready, not rerun |
| rehearsal-D | PAM50 relabelled to Basal for 4 tumors; 3 Her2 copy-number profiles replaced by duplicates | A1 Ready, not rerun; A2 Blocked (PAM50 label) |
| rehearsal-E | 1 RNA swap; histological type relabelled for 2 tumors; 2 Basal protein profiles replaced by duplicates | A1 Blocked (duplicates); A2 Ready; RNA and histology changes reported but affect no analysis |

Run all three and grade against each release's CHANGES.json (only after the run):
```bash
bash scripts/rehearse.sh
```
