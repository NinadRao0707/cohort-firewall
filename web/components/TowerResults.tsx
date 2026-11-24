"use client";
import { useState } from "react";
import type { Verdict } from "@/lib/types";
import type { FindingsDoc, TowerAnalysis, TowerFinding } from "@/lib/tower";
import { CertificatePanel } from "./CertificatePanel";
import { LedgerPanel } from "./LedgerPanel";
import { ShareableSummary } from "./ShareableSummary";
import { ReleaseReview } from "./ReviewPanel";
import { NextSteps } from "./Summary";
import { Tabs } from "./Tabs";
import { VerdictGate } from "./VerdictGate";

const TO_ENGINE: Record<string, Verdict> = {
  Ready: "READY", Conditional: "CONDITIONAL", Blocked: "BLOCKED", "Insufficient Evidence": "INSUFFICIENT_EVIDENCE",
};
const TOWER_LINE: Record<Verdict, string> = {
  READY: "Nothing in this release affects the protected analyses.",
  CONDITIONAL: "Usable only after the changes below are reviewed.",
  BLOCKED: "At least one protected analysis can't be trusted on this release yet.",
  INSUFFICIENT_EVIDENCE: "The comparison can't be trusted, so nothing passes by default.",
};
const STATUS: Record<string, string> = { changed: "Rerun, result changed", unchanged: "Rerun, result unchanged", not_rerun: "Not rerun" };
const show = (v: unknown) => (typeof v === "object" && v !== null
  ? Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} ${x}`).join(", ") : String(v ?? "–"));

function AnalysisRow({ a }: { a: TowerAnalysis }) {
  const keys = Object.keys(a.before ?? {}).filter((k) => !["analysis", "inputs", "n_sample_ids"].includes(k));
  const moved = a.after ? keys.filter((k) => show(a.before![k]) !== show(a.after![k])) : [];
  return (
    <li className="analysis" data-verdict={TO_ENGINE[a.verdict ?? "Ready"]}>
      <div className="analysis-head">
        <span className="analysis-id">{a.id}</span>
        <span className="analysis-verdict">{a.verdict}</span>
        <span className="quiet">{STATUS[a.status]}</span>
      </div>
      <p className="analysis-desc">{a.description}</p>
      {a.status === "not_rerun" ? <p className="quiet">{a.reason}</p> : (
        <ul className="plain-list">{(a.verdict_rules ?? []).map((r) => <li key={r.rule_id}><strong>{r.rule_id}</strong> {r.reason}</li>)}</ul>
      )}
      {moved.length > 0 && (
        <p className="moved">{moved.map((k) => <span key={k}>{k.replaceAll("_", " ")}: {show(a.before![k])} → <b>{show(a.after![k])}</b></span>)}</p>
      )}
      {a.x_impact?.noise && (
        <div className="impact">
          <p><span className="impact-k">How much it moved</span>
            <span className="impact-pill" data-label={a.x_impact.noise.label}>{a.x_impact.noise.ratio}× sampling noise · {a.x_impact.noise.label}</span></p>
          <p className="quiet">{a.x_impact.noise.kind === "scalar"
            ? `${a.x_impact.noise.metric} changed ${a.x_impact.noise.delta}; sampling alone moves it about ${a.x_impact.noise.noise} (${a.x_impact.noise.noise_name}, from rerunning the organizers' code on resampled baseline data).`
            : `The mix shifted ${a.x_impact.noise.shift} points; resampling alone shifts it up to ${a.x_impact.noise.noise} points 95% of the time.`}
            {a.x_impact.noise.label !== "beyond sampling noise" && a.verdict !== "Ready" ? " A small shift doesn't make it safe: the verdict comes from what changed, not how much." : ""}</p>
        </div>
      )}
      {a.x_impact?.repair && (
        <div className="impact">
          <p><span className="impact-k">If you apply the repairs</span>
            {a.x_impact.repair.back_to_baseline ? "it returns to its baseline value." : `it becomes ${a.x_impact.repair.after_all_repairs} (baseline ${a.x_impact.repair.baseline}).`}</p>
          {a.x_impact.repair.by_kind.length > 0 && (
            <p className="quiet">Share of the shift: {a.x_impact.repair.by_kind.map((k) => `${k.kind.replaceAll("_", " ")} ${k.share_of_shift_pct}% (${k.findings.join(", ")})`).join("; ")}.</p>
          )}
        </div>
      )}
      {a.before && (
        <details className="fold"><summary>All values</summary>
          <div className="table-scroll"><table className="checks compare">
            <thead><tr><th scope="col">Value</th><th scope="col">Baseline</th><th scope="col">New release</th></tr></thead>
            <tbody>{keys.map((k) => (
              <tr key={k}><th scope="row">{k.replaceAll("_", " ")}</th><td>{show(a.before![k])}</td><td>{a.after ? show(a.after[k]) : "not rerun"}</td></tr>
            ))}</tbody>
          </table></div>
        </details>
      )}
    </li>
  );
}

function ChangeRow({ f }: { f: TowerFinding }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="finding" data-severity={f.severity}>
      <button type="button" className="finding-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="finding-head"><span className="rule-id">{f.id}</span>
          <span className="finding-level">{f.severity} · {f.affects_analyses?.length ? `affects ${f.affects_analyses.join(", ")}` : "affects no protected analysis"}</span></span>
        <span className="finding-reason">{f.summary}</span>
        <span className="finding-more" aria-hidden="true">{open ? "Hide details" : "Details"}</span>
      </button>
      {open && (
        <div className="finding-body">
          {f.x_severity_reason && <p><span>Why this severity:</span> {f.x_severity_reason.replace(/^(High|Medium|Low): /, "")}</p>}
          <p><span>Confidence:</span> {f.confidence}{f.x_confidence_reason ? `. ${f.x_confidence_reason}` : ""}</p>
          <p><span>Samples that changed:</span> <code>{f.evidence.filter((e) => e.kind === "sample").map((e) => e.id).join(", ") || "file-level"}</code></p>
          {f.evidence.filter((e) => e.note).map((e, i) => <p key={i} className="quiet">{e.id}: {e.note}</p>)}
          {typeof f.x_p_by_chance === "number" && (
            <p><span>Chance this is random:</span> p = {f.x_p_by_chance.toPrecision(2)} (hypergeometric test).
              {f.x_p_by_chance < 0.05 ? " Unlikely by chance: fits a targeted removal or a filtering error; the tool can't tell which." : " Consistent with chance."}</p>
          )}
          {f.limitation && <p><span>Limitation:</span> {f.limitation}</p>}
        </div>
      )}
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
      <VerdictGate verdict={verdict} line={TOWER_LINE[verdict]} summary={doc.plain_summary}
                   cant={["which release is correct, so every repair needs a person's decision",
                          "for sure whether a near-match swap is real, so probable swaps need checking against the source",
                          ...(doc.not_compared?.length ? [`anything about ${doc.not_compared.join(", ")}, which this release doesn't include`] : [])]}
                   question={`${release?.name} compared with ${baseline?.name}${doc.baseline_unverified_files?.length
                     ? " (baseline does not match the frozen checksums)" : ""}${doc.timing_seconds ? `, ${doc.timing_seconds.total} s` : ""}`} />
      <Tabs tabs={[
        { id: "analyses", label: "Analyses", count: doc.analyses?.length ?? 0,
          content: <ul className="analyses">{(doc.analyses ?? []).map((a) => <AnalysisRow key={a.id} a={a} />)}</ul> },
        { id: "steps", label: "Next steps", count: doc.next_steps?.length ?? 0, content: <NextSteps steps={doc.next_steps} /> },
        { id: "changes", label: "Changes", count: doc.findings.length, content: (
          <>
            {findings.length
              ? <ul className="findings">{findings.map((f) => <ChangeRow key={f.id} f={f} />)}</ul>
              : <p className="quiet">No differences from the baseline.</p>}
            {(doc.x_summaries?.length ?? 0) > 0 && (
              <details className="fold">
                <summary>Summaries ({doc.x_summaries!.length}): they restate the changes above, so they aren&apos;t counted as separate problems</summary>
                <ul className="findings">{doc.x_summaries!.map((f) => <ChangeRow key={f.id} f={f} />)}</ul>
              </details>
            )}
          </>
        ) },
        { id: "review", label: "Review", content: <ReleaseReview key={(doc.certificate as { cert_id?: string } | undefined)?.cert_id ?? "r"} doc={doc} /> },
        { id: "record", label: "Record", content: (
          <>
            <div className="actions"><button type="button" onClick={download}>Download findings.json</button></div>
            <p className="quiet">Shared format v{doc.format_version}, for a Repair Review Desk or any reviewer.</p>
            <ShareableSummary data={doc.x_shareable_summary} name={release?.name ?? "release"} />
            <details className="fold"><summary>Limitations of this check</summary>
              <ul className="plain-list">{(doc.limitations ?? []).map((l) => <li key={l}>{l}</li>)}</ul></details>
            {doc.certificate ? <CertificatePanel cert={doc.certificate as never} /> : null}
            <LedgerPanel entry={doc.x_ledger} />
          </>
        ) },
      ]} />
    </div>
  );
}
