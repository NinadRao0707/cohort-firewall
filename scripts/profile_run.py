"""Where does the time go? Times each stage of a release comparison on this machine.

  python scripts/profile_run.py ~/oncosys-hackathon-challenge/envelopes/opened/practice/release
"""
import sys
import time
from pathlib import Path

t_start = time.time()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from cohort_firewall.tower import releases as rel  # noqa: E402
import cohort_firewall.tower.run as run  # noqa: E402
from cohort_firewall.tower import impact  # noqa: E402

print(f"python + imports          {time.time() - t_start:5.2f} s")
print(f"fingerprint version       {rel.CACHE_VERSION}   (fp2 = new fast version)")
b = Path(sys.argv[1]).expanduser()
print("\nPer file in the new release (fast path = numeric fingerprint):")
for f in sorted(p.name for p in b.iterdir() if p.name in rel.LAYOUT):
    orient = rel.LAYOUT[f][0]
    t = time.time()
    how = "rows"
    if orient == "columns":
        try:
            rel._load_matrix_numeric(b / f, f)
            how = "fast path"
        except Exception as e:
            how = f"FALLBACK ({type(e).__name__}: {str(e)[:60]})"
            rel._load_matrix(b / f, f)
    else:
        rel._load_rows(b / f, f, rel.LAYOUT[f][1])
    t1 = time.time() - t
    t = time.time(); rel.file_sha256(b / f); rel.content_sha256(b / f); t2 = time.time() - t
    print(f"  {f:30s} fingerprint {t1:5.2f} s   checksums {t2:5.2f} s   {how}")

T = {}
def wrap(mod, name):
    fn = getattr(mod, name)
    def w(*a, **k):
        t = time.time(); r = fn(*a, **k); T[name] = T.get(name, 0) + time.time() - t; return r
    setattr(mod, name, w)
for mod, name in [(run, "load_release"), (run, "diff_releases"), (run, "evaluate_analyses"),
                  (run, "build_findings"), (impact, "noise"), (impact, "repair_simulation")]:
    wrap(mod, name)
repo = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path.home() / "oncosys-hackathon-challenge"
t = time.time()
doc = run.run_tower(repo, b)
total = time.time() - t
print(f"\nFull comparison           {total:5.2f} s")
for k, v in T.items():
    print(f"  {k:24s}{v:5.2f} s")
print(f"(load_release includes the cached baseline: {doc['timing_seconds']})")
