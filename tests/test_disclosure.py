"""Small-cell suppression keeps IDs, decimals and p-values, hides counts 1-10. Run: python tests/test_disclosure.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cohort_firewall.disclosure import suppress  # noqa: E402

CASES = [
    ("Her2 lost 5 of 61 genuine profiles", "Her2 lost <11 of 61 genuine profiles"),
    ("1 sample swap(s) and 10 copies", "<11 sample swap(s) and <11 copies"),
    ("A1 moved 0.31x; F13 and A2", "A1 moved 0.31x; F13 and A2"),
    ("probability 1.4e-05 and 8.2%", "probability 1.4e-05 and 8.2%"),
    ("count unchanged (747); 0 findings; 52 of 508", "count unchanged (747); 0 findings; 52 of 508"),
    ("TCGA-A8-A09K-01 swapped", "TCGA-A8-A09K-01 swapped"),
]


def run():
    ok = True
    for text, want in CASES:
        got = suppress(text)
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {text!r} -> {got!r}")
    return ok


def test_disclosure():
    assert run()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
