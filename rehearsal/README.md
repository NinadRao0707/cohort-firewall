# Rehearsal releases

Private releases built with the event's own `make_release.py --config`, using change types and files
that practice-B doesn't use. They check the Control Tower on input it was not tuned for.

| Release | Changes | Result |
|---|---|---|
| `rehearsal-C.json` | ER status relabelled to Negative for 3 tumors; 2 protein swaps | 5 / 5 found; A1 Blocked, A2 not rerun |
| `rehearsal-D.json` | PAM50 relabelled to Basal for 4 tumors; 3 Her2 copy-number profiles replaced by copies | 10 / 10 found; A1 not rerun, A2 Blocked |
| `rehearsal-E.json` | 1 RNA swap; histology relabelled for 2 tumors; 2 Basal protein profiles replaced | 7 / 7 found; A1 Blocked, A2 not rerun |

No unexplained findings in any of them.

## Run
```bash
bash scripts/rehearse.sh
```
Each release is built in the challenge repository, compared, validated and graded against its own
`CHANGES.json`, which is read only after the run.
