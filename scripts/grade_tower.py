"""Grade a findings.json against a release's CHANGES.json (use only AFTER the tool has run).

  python scripts/grade_tower.py findings.json path/to/release/CHANGES.json

Reports each answer-key change as found / missed, and any finding not explained by the key
(summary findings are listed separately because they restate other findings).
"""
import json
import sys


def ids(f):
    return {e["id"] for e in f.get("evidence", [])}


def main(findings_path, changes_path):
    doc = json.load(open(findings_path))
    key = json.load(open(changes_path))
    fs = doc["findings"]
    used, rows = set(), []

    def find(pred):
        hit = [f for f in fs if pred(f)]
        used.update(f["id"] for f in hit)
        return hit

    for ch in key["changes"]:
        t, file = ch["type"], ch["file"]
        if t == "swap_samples":
            ok = find(lambda f: f.get("kind") == "sample_swap" and ids(f) == set(ch["samples"]))
            rows.append((f"swap {ch['samples'][0]} <-> {ch['samples'][1]} ({file})", bool(ok)))
        elif t == "replace_with_duplicates":
            for d in ch["duplicates"]:
                ok = find(lambda f, d=d: f.get("kind") == "duplicate" and {d["new_id"], d["copied_from"]} <= ids(f))
                rows.append((f"duplicate {d['new_id']} = copy of {d['copied_from']} ({file})", bool(ok)))
            for s in ch["removed"]:
                ok = find(lambda f, s=s: f.get("kind") == "membership_change" and s in ids(f)
                          and not f.get("x_summary_of_other_findings"))
                rows.append((f"removed {s} ({file})", bool(ok)))
        elif t == "relabel_clinical":
            for s, old in ch["before"].items():
                ok = find(lambda f, s=s: f.get("kind") in {"label_conflict", "other"} and s in ids(f)
                          and ch["column"] in f["summary"])
                rows.append((f"relabel {s} {ch['column']}: {old!r} -> {ch['new_value']!r}", bool(ok)))
    found = sum(ok for _, ok in rows)
    print(f"Answer key: {found}/{len(rows)} changes found")
    for what, ok in rows:
        print(f"  {'FOUND ' if ok else 'MISSED'} {what}")
    extra = [f for f in fs if f["id"] not in used and not f.get("x_summary_of_other_findings")]
    summaries = [f for f in fs if f.get("x_summary_of_other_findings")]
    print(f"Unexplained findings (possible false positives): {len(extra)}")
    for f in extra:
        print(f"  {f['id']} {f['summary']}")
    print(f"Summary findings (restate others): {len(summaries)}")
    print("Analyses:", ", ".join(f"{a['id']}={a['verdict']} ({a['status']})" for a in doc.get("analyses", [])))
    return found == len(rows) and not extra


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
