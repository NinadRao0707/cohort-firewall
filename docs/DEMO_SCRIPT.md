# Demo script

Three minutes, then two minutes of questions. Rubric points are in brackets.

**Before you start:** run `bash scripts/run.sh`, open **http://localhost:3000/tower** and
**http://localhost:3000** in two tabs, and open the practice envelope once so it's cached.

## 0:00 – 0:15 · The user and the problem
"Our user is a research engineer who looks after the TCGA-BRCA dataset. A new release arrives. Before
anyone reruns an analysis, they need to know what changed, what it breaks, and whether the data can
still answer the questions people ask."

## 0:15 – 1:00 · Release check  [Finding data problems 20 · Reasoning 20 · Next steps 10]
1. **+ Open envelope** → `practice` → **Open and compare**.
2. Read the plain-English summary: the protein sample count is unchanged at 747, but 5 samples were
   removed and 5 copies added. "A count check alone would miss this."
3. **Analyses** tab: A1 is **Blocked**, with its moved values highlighted. A2 is **Ready, not rerun**:
   nothing it reads changed.
4. **Next steps** tab: restore 2 swapped profiles, exclude 5 copied IDs.

## 1:00 – 1:45 · Question check  [Reasoning 20 · Finding data problems 20]
1. **Examples** → *PAM50 subtype mix* → **Check readiness**: **Conditional**. "The two PAM50 calls in
   this release disagree for 10% of tumors: the organizers' own example, found on their data."
2. **Examples** → *2-year progression, fairness across race*: **Insufficient Evidence**. "The release
   doesn't record race, so the tool says it can't answer this, and why."
3. Change the **Use** chip to *Support a clinical decision*: **Blocked**.

## 1:45 – 2:15 · Evidence  [Evidence and sources 15]
1. **Samples** tab: records left after each step, and **Download sample list**.
2. **Findings** tab → **Details** on one finding: fields, rule, measured value with its 95% range,
   and the check's limitation.

## 2:15 – 2:40 · Human review  [Safety and uncertainty 15]
**Review** tab: a Blocked result offers only *Reject* or *Ask for more evidence*. Tick
**All findings**, add a note and **Record review**; the review is signed and saved with the evidence.

## 2:40 – 3:00 · Close  [Working tool 15 · Communication 5]
"44 planted changes across five runs, all found, none invented. A fresh clone runs in four commands,
and findings.json goes straight to a Repair Review Desk."

## Likely questions
| Question | Short answer |
|---|---|
| Why these thresholds? | Defaults in a versioned rule file; every finding shows the rule and the measured value, and borderline cases are marked |
| Why not let an AI decide? | Rules are auditable and repeatable, and text hidden in the data can't talk them into a verdict |
| What can it miss? | A swap that also edits values shows as value edits; identifier detection is pattern-based. Both are in the Limitations panel |
| 10% vs the organizers' 11%? | We count primary tumors with both PAM50 calls (52 of 508); their denominator may differ |
| Does Ready mean safe to deploy? | No. Ready means fit for this research question, and a person still reviews |
| Can you accept a problem to get Ready? | Only listed Conditional ones; Blocked never. It stays visible, and approval then needs a written reason |

For the live envelope test, see [`HIDDEN_TEST.md`](HIDDEN_TEST.md).
