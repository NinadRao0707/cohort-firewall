# Demo script

Three minutes, then two minutes of questions. Rubric points are in brackets.

**Before you start:** run `bash scripts/run.sh`, open **http://localhost:3000/tower** and
**http://localhost:3000** in two tabs, and open the practice envelope once so it's cached.

## 0:00 – 0:15 · The user and the problem
"Our user is a research engineer who looks after the TCGA-BRCA dataset. A new release arrives. Before
anyone reruns an analysis, they need to know what changed, what it breaks, and whether the data can
still answer the questions people ask."

## 0:15 – 1:00 · Release check  [Finding data problems 20 · Reasoning 20 · Next steps 10]
Every working tool finds the same changes, so spend the time on what happens after.
1. **+ Open envelope** → `practice` → **Open and compare**. "It finds the swap, the 5 copies and the
   5 removals, and the sample count stayed at 747, so a count check would miss all of it."
2. **Why it matters:** "All 5 removed samples are Her2, which loses 8% of its profiles while every
   other subtype loses under 1%. Anyone studying Her2 is hit far harder than the total suggests."
   A1 is **Blocked** (difference 3.051 → 3.019); A2 is **left alone**, because nothing it reads changed.
3. **What to do next:** **Next steps** tab: restore 2 swapped profiles, exclude 5 copied IDs, check
   the removals. **Changes → Details** shows why each one is high, medium or low.
4. **What it can't tell you:** read the line under the summary: which release is correct, and edits
   hidden inside a swapped profile.

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
**Record → Verify the ledger:** "Every check and every decision goes into a signed, hash-chained
ledger. If anyone later changes a verdict or deletes a review, the chain breaks at that entry."

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
| How do you know nobody changed a result later? | Results and reviews are signed, and every one is chained in the audit ledger; `python scripts/tamper_demo.py` shows a changed verdict being caught |
| Can you accept a problem to get Ready? | Only listed Conditional ones; Blocked never. It stays visible, and approval then needs a written reason |

For the live envelope test, see [`HIDDEN_TEST.md`](HIDDEN_TEST.md).
