# User test: do people reach the right conclusion?

Dashboard rule 98 asks whether users reach correct conclusions, not just whether the tool runs.
This is a 5-minute protocol for one person who hasn't seen the tool, observed by one team member.
**Status: protocol ready; results below are filled in only from real sessions.**

## Setup
`bash scripts/run.sh`, open **http://localhost:3000/tower**. Give the participant only this sentence:
"A new release of a cancer dataset arrived. Use this tool to decide whether it's safe to use." Don't help.

## Tasks and expected conclusions
| # | Task | Correct conclusion | Shows that |
|---|---|---|---|
| 1 | Open envelope `practice` (code `orange meadow pilot lantern`). Can the release be used for A1? | No: A1 is Blocked because measurements are on the wrong samples | The verdict and reason are findable |
| 2 | Is A2 affected? | No: nothing A2 reads changed, so it wasn't rerun | "Not rerun" is understood, not read as a failure |
| 3 | Does the small change in A1's value mean it's safe? | No: the shift is within sampling noise, but the verdict comes from what changed | Size vs. integrity is understood |
| 4 | What should be fixed first? | Restore the swapped profiles (Next steps 1) | Next steps are actionable |
| 5 | Was the Her2 loss likely random? | Unlikely by chance; could be targeted or a filtering bug; the tool can't say which | The limit on intent is understood |
| 6 | On Question check, can this data study fairness across race? | No: Insufficient evidence, race isn't recorded | Question-specific reasoning is understood |

## Record
| Date | Participant role | Tasks correct (of 6) | Where they hesitated | Change we made |
|---|---|---|---|---|
| | | | | |

A task counts as correct only if the participant states the conclusion in their own words.
