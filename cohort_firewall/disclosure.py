"""Small-cell suppression for summaries meant to be shared beyond the review team.

Counts from 1 to 10 are shown as "<11", following the CMS cell-size suppression policy ("no cell
less than 11 may be displayed"). Sample IDs, decimals, percentages, p-values, rule IDs (A1, F13) and
zero are left alone. This applies to the shareable summary only: the evidence record and findings.json
keep exact counts and sample IDs, because the reviewer and the Repair Review Desk need them.
"""
import re

_SMALL = re.compile(r"(?<![\w.#\-+/<])([1-9]|10)(?![\w.%×/:])")


def suppress(text: str) -> str:
    return _SMALL.sub("<11", text or "")


NOTE = ("Counts from 1 to 10 are shown as <11 (CMS small-cell suppression). A percentage next to a hidden "
        "count can still reveal it, so a person should read this before sharing. The full evidence record "
        "keeps exact counts and sample IDs for reviewers.")
