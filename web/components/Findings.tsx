"use client";
import { useState } from "react";
import { VERDICT_COPY, type Finding } from "@/lib/types";

function Row({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="finding" data-verdict={f.verdict} data-accepted={f.accepted ? "true" : undefined}>
      <button type="button" className="finding-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="finding-head">
          <span className="rule-id">{f.rule_id}</span>
          <span className="finding-level">{f.accepted ? "Accepted by the card" : VERDICT_COPY[f.verdict].label}
            {f.borderline ? ", borderline" : ""}</span>
        </span>
        <span className="finding-reason">{f.reason}</span>
        <span className="finding-more" aria-hidden="true">{open ? "Hide details" : "Details"}</span>
      </button>
      {open && (
        <div className="finding-body">
          {f.effect_on_intended_use && <p><span>Why it matters:</span> {f.effect_on_intended_use}</p>}
          {f.remedy && <p><span>To fix:</span> {f.remedy}</p>}
          {f.reconsider && <p><span>What would change it:</span> {f.reconsider}</p>}
          {f.check_performed && (
            <dl className="evidence-grid">
              <dt>Check</dt><dd>{f.check_performed}</dd>
              <dt>Fields</dt><dd><code>{(f.fields_used ?? []).join(", ") || "none"}</code></dd>
              <dt>Affected</dt><dd>{f.rows_or_groups_affected || "whole question"}</dd>
              <dt>Rule</dt><dd><code>{f.rule_condition}</code></dd>
              <dt>Uncertainty</dt><dd>{f.uncertainty}</dd>
              <dt>Confidence</dt><dd>{f.confidence}</dd>
              <dt>Limitation</dt><dd>{f.limitation}</dd>
            </dl>
          )}
        </div>
      )}
    </li>
  );
}

export function Findings({ findings, csv, name }: { findings: Finding[]; csv?: string; name?: string }) {
  function download() {
    if (!csv) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `findings-${name ?? "result"}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  if (findings.length === 0) return <p className="quiet">Every check that applies to this question passed.</p>;
  return (
    <>
      <ul className="findings">{findings.map((f, i) => <Row key={`${f.rule_id}-${i}`} f={f} />)}</ul>
      {csv && <div className="actions"><button type="button" className="secondary" onClick={download}>Download findings (CSV)</button></div>}
    </>
  );
}
