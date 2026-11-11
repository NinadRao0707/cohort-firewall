"""Treat everything that comes from the dataset as data, never as instructions.

Anything derived from the dataset (column names, category labels, cell snippets)
passes through here before it can reach the LLM report writer or the UI.
"""
import re

_SAFE_IDENT = re.compile(r"[^A-Za-z0-9_\-.,()%+ ]")

# Phrases that suggest a cell or description is trying to talk to a model or reviewer.
INJECTION_PATTERNS = [
    r"ignore (all|any|previous|prior|the above)",
    r"disregard (all|any|previous|prior|the)",
    r"\bsystem\s*(prompt|message)?\s*:",
    r"\bassistant\s*:",
    r"mark (this|the) (dataset|data|cohort)? ?(as )?(ready|approved|safe)",
    r"\bverdict\b",
    r"you are (now )?(an?|the) ",
    r"override (the )?(checks?|rules?|policy|firewall)",
    r"</?(system|instructions?|prompt)>",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def safe_ident(value: object, max_len: int = 48) -> str:
    """Reduce a column name or category label to a short, inert identifier."""
    s = re.sub(r"\s+", " ", _SAFE_IDENT.sub("_", str(value))).strip()[:max_len]
    return s or "_"


def looks_like_injection(text: str) -> bool:
    return bool(_INJ.search(text or ""))
