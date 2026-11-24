"""The hosted demo must only ever ship synthetic data. Run: python tests/test_public_demo.py

Checks that the web app's synthetic list and the build's allow-list match, that every allow-listed
file exists, and that none of them contains a TCGA barcode (real IDs stay local)."""
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
BARCODE = re.compile(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}")


def names(path: Path) -> set[str]:
    text = path.read_text()
    block = text[text.index("[", text.index("Set(")) : text.index("]", text.index("Set("))]
    return set(re.findall(r'"([^"]+)"', block))


def run():
    app, build = names(WEB / "lib" / "demo.ts"), names(WEB / "scripts" / "prepare-demo.mjs")
    checks = [("app list and build allow-list match", app == build)]
    files = [WEB / "public" / "samples" / f"{n}.json" for n in sorted(build)]
    missing = [f.name for f in files if not f.exists()]
    checks.append((f"every allow-listed sample exists{': missing ' + ', '.join(missing) if missing else ''}", not missing))
    leaks = [f.name for f in files if f.exists() and BARCODE.search(f.read_text())]
    checks.append((f"no TCGA barcode in any hosted sample{': ' + ', '.join(leaks) if leaks else ''}", not leaks))
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return all(ok for _, ok in checks)


def test_public_demo():
    assert run()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
