# Changelog

## 0.2.0 (post-hackathon, Nov 2026)
Changes made after judging, in response to the organizers' written feedback.

- **Review on every verdict.** Every decision, Ready included, needs a named reviewer and a written
  note; Ready results are marked "review required".
- **Confidence follows the evidence.** Exact swaps and copies are high; probable swaps and copies of a
  profile several samples share are medium; subgroup losses follow their chance test. Each finding
  states its reason (`x_confidence_reason`).
- **Summaries kept apart.** Findings that only restate others move to `x_summaries` (IDs S1, S2…), so a
  Repair Review Desk never counts one problem twice. `--summary-findings` restores the old layout.
- **Probable swaps.** A near-match pass reports a swap hidden by small value edits as a probable swap
  (medium confidence). A negative-control test checks that ordinary edits aren't called swaps.
- **Clearer release results.** The summary opens with one sentence (verdict, main reason, first step);
  "check against the source" is split by what changed; every next step says what would change the verdict.
- **Pinned versions.** `requirements.lock` holds exact package versions; `setup.sh` installs it when present.
- Engine version 0.1.0 → 0.2.0, so certificates show which version produced a result.

## 0.1.0 (code freeze, Nov 14, 2026)
The judged submission, commit `ab5084f`. Second place, Track 1 (Best Cohort Firewall).
