"use client";
import { useState } from "react";
import type { Verdict } from "@/lib/types";
import type { FindingsDoc, TowerAnalysis, TowerFinding } from "@/lib/tower";
import { CertificatePanel } from "./CertificatePanel";
import { ReleaseReview } from "./ReviewPanel";
import { VerdictGate } from "./VerdictGate";

const TO_ENGINE: Record<string, Verdict> = {
  Ready: "READY", Conditional: "CONDITIONAL", Blocked: "BLOCKED", "Insufficient Evidence": "INSUFFICIENT_EVIDENCE",
};
const TOWER_LINE: Record<Verdict, string> = {
  READY: "No change affects the protected analyses. They can be reused on the new release.",
  CONDITIONAL: "At least one analysis is usable on the new release only after the changes below are reviewed.",
  BLOCKED: "At least one protected analysis can't be trusted on the new release until the findings are resolved.",
  INSUFFICIENT_EVIDENCE: "The comparison can't be trusted, so nothing passes by default.",
};
const STATUS: Record<string, string> = {
  changed: "Rerun: result changed", unchanged: "Rerun: result unchanged", not_rerun: "Not rerun",
};

function ResultTable({ before, after }: { before?: Record<string, unknown>; after?: Record<string, unknown> }) {
  if (!before) return null;
  const keys = Object.keys(before).filter((k) => !["analysis", "inputs"].includes(k));
  const show = (v: unknown) => (typeof v === "object" && v !== null ? Object.entries(v as Record<string, unknown>)
    .map(([k, x]) => `${k} ${x}`).join(", ") : String(v ?? "–"));
  return (
    <div className="table-scroll">
      <table className="checks compare">
        <thead><tr><th scope="col">Value</th><th scope="col">Baseline</th><th scope="col">New release</th></tr></thead>
        <tbody>
          {keys.map((k) => {
            const b = show(before[k]); const a = after ? show(after[k]) : "not rerun";
            return (
              <tr key={k} data-moved={after && a !== b ? "true" : undefined}>
                <th scope="row">{k.replaceAll("_", " ")}</th><td>{b}</td><td>{a}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AnalysisCard({ a }: { a: TowerAnalysis }) {
  const v = TO_ENGINE[a.verdict ?? "Ready"];
  return (
    <li className="analysis" data-verdict={v}>
      <div className="analysis-head">
        <span className="analysis-id">{a.id}</span>
        <span className="analysis-verdict">{a.verdict}</span>
        <span className="quiet">{STATUS[a.status]}</span>
      </div>
      {a.description && <p className="analysis-desc">{a.description}</p>}
      <p className="quiet">{a.reason}</p>
      {a.verdict_rules && a.verdict_rules.length > 0 && (
        <ul className="plain-list rules">
          {a.verdict_rules.map((r) => (
            <li key={r.rule_id}><span className="rule-id">{r.rule_id}</span> {r.reason} <em>To fix:</em> {r.remedy}</li>
          ))}
        </ul>
      )}
      <ResultTable before={a.before} after={a.after} />
      <p className="review" data-level={a.needs_human_review ? "required" : "recommended"}>
        <span>Human review {a.needs_human_review ? "required" : "recommended"}.</span>{" "}
        {a.needs_human_review ? "Do not use this analysis on the new release until a person resolves the findings."
          : "No change touches this analysis; a person should still confirm before relying on it."}
      </p>
    </li>
  );
}

function FindingRow({ f }: { f: TowerFinding }) {
  const [open, setOpen] = useState(false);
  const samples = f.evidence.filter((e) => e.kind === "sample");
  return (
    <li className="finding" data-severity={f.severity}>
      <div className="finding-head">
        <span className="rule-id">{f.id}</span>
        <span className="finding-level">{f.severity} severity · {f.kind?.replaceAll("_", " ")}</span>
      </div>
      <p className="finding-reason">{f.summary}</p>
      <p className="finding-remedy">
        <span>Affects:</span> {f.affects_analyses?.length ? f.affects_analyses.join(", ") : "no protected analysis"}
        {f.not_affected_analyses?.length ? <> · <span>Not affected:</span> {f.not_affected_analyses.join(", ")}</> : null}
      </p>
      {samples.length > 0 && (
        <button type="button" className="link" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Show"} evidence ({samples.length} sample{samples.length === 1 ? "" : "s"})
        </button>
      )}
      {open && (
        <ul className="evidence">
          {f.evidence.map((e, i) => (
            <li key={i}><code>{e.id}</code> {e.file ? `in ${e.file}` : ""} {e.release ? `(${e.release})` : ""} {e.note ?? ""}</li>
          ))}
        </ul>
      )}
      {f.limitation && <p className="finding-limit"><span>Limitation:</span> {f.limitation}</p>}
    </li>
  );
}

export function TowerResults({ doc }: { doc: FindingsDoc }) {
  const verdict = TO_ENGINE[doc.verdict ?? "Ready"];
  const [baseline, release] = doc.data.releases;
  const order = { high: 0, medium: 1, low: 2, none: 3 };
  const findings = [...doc.findings].sort((a, b) => order[a.severity] - order[b.severity]);

  function download() {
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `findings-${release?.name ?? "release"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="results">
      <div>
        <VerdictGate verdict={verdict} question={doc.question} line={TOWER_LINE[verdict]} />
        <p className="quiet">
          Compared <strong>{release?.name}</strong> with <strong>{baseline?.name}</strong>
          {doc.baseline_unverified_files?.length
            ? ` (baseline does NOT match the frozen checksums: ${doc.baseline_unverified_files.join(", ")})`
            : " (baseline matches the event's frozen checksums)"}.
          {doc.timing_seconds ? ` Took ${doc.timing_seconds.total} s.` : ""}
        </p>
      </div>

      <section className="block">
        <h3>Protected analyses</h3>
        <ul className="analyses">{(doc.analyses ?? []).map((a) => <AnalysisCard key={a.id} a={a} />)}</ul>
      </section>

      <section className="block">
        <h3>What changed ({doc.findings.length} finding{doc.findings.length === 1 ? "" : "s"})</h3>
        {findings.length === 0 ? <p className="quiet">No differences from the baseline.</p> :
          <ul className="findings">{findings.map((f) => <FindingRow key={f.id} f={f} />)}</ul>}
      </section>

      {doc.repairs && doc.repairs.length > 0 && (
        <section className="block">
          <h3>Proposed repairs (a reviewer decides)</h3>
          <div className="table-scroll">
            <table className="checks">
              <thead><tr><th scope="col">Repair</th><th scope="col">Action</th><th scope="col">Samples</th><th scope="col">Resolves</th></tr></thead>
              <tbody>
                {doc.repairs.map((r) => (
                  <tr key={r.id}>
                    <th scope="row">{r.id}</th>
                    <td>{r.action.replaceAll("_", " ")}</td>
                    <td><code>{r.targets.slice(0, 3).map((t) => t.id).join(", ")}{r.targets.length > 3 ? ` +${r.targets.length - 3}` : ""}</code></td>
                    <td>{r.addresses.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="block">
        <details className="limits" open>
          <summary>Limitations of this check</summary>
          <ul className="plain-list">{(doc.limitations ?? []).map((l) => <li key={l}>{l}</li>)}</ul>
        </details>
      </section>

      <section className="block">
        <h3>Hand-off</h3>
        <p className="quiet">Shared findings format v{doc.format_version}, for a Repair Review Desk or any reviewer.</p>
        <div className="cert-actions"><button type="button" onClick={download}>Download findings.json</button></div>
      </section>

      <ReleaseReview key={(doc.certificate as { cert_id?: string } | undefined)?.cert_id ?? "r"} doc={doc} />

      {doc.certificate ? <CertificatePanel cert={doc.certificate as never} /> : null}
    </div>
  );
}
