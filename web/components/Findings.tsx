"use client";
import { useState } from "react";
import { VERDICT_COPY, type Finding } from "@/lib/types";

function Evidence({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  if (!f.check_performed) return null;
  return (
    <>
      <button type="button" className="link" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} the evidence behind this
      </button>
      {open && (
        <dl className="evidence-grid">
          <dt>Check performed</dt><dd>{f.check_performed}</dd>
          <dt>Fields used</dt><dd><code>{(f.fields_used ?? []).join(", ") || "none"}</code></dd>
          <dt>Rows or groups affected</dt><dd>{f.rows_or_groups_affected || "whole question"}</dd>
          <dt>Measured</dt><dd><code>{Object.entries(f.measured ?? {}).map(([k, v]) => `${k} = ${v}`).join(", ")}</code></dd>
          <dt>Decision rule</dt><dd><code>{f.rule_id}: {f.rule_condition}</code></dd>
          <dt>Confidence</dt><dd>{f.confidence}</dd>
          <dt>Uncertainty</dt><dd>{f.uncertainty}</dd>
          <dt>Limitation of this check</dt><dd>{f.limitation}</dd>
          <dt>Source</dt><dd>{f.evidence_or_source}</dd>
        </dl>
      )}
    </>
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
  if (findings.length === 0) {
    return (
      <section className="block">
        <h3>Why</h3>
        <p className="quiet">Every check that applies to this question passed under the current policy.</p>
      </section>
    );
  }
  return (
    <section className="block">
      <h3>Why</h3>
      <ul className="findings">
        {findings.map((f, i) => (
          <li key={`${f.rule_id}-${i}`} className="finding" data-verdict={f.verdict} data-accepted={f.accepted ? "true" : undefined}>
            <div className="finding-head">
              <span className="rule-id">{f.rule_id}</span>
              <span className="finding-level">{VERDICT_COPY[f.verdict].label}{f.accepted ? " · accepted by the question card" : ""}
                {f.materiality ? ` · ${f.materiality} materiality` : ""}
                {f.borderline ? " · borderline (the 95% range crosses the rule's threshold)" : ""}</span>
            </div>
            {f.accepted && <p className="finding-remedy"><span>Accepted as:</span> {f.accepted_as}. Still shown so a reviewer can confirm it.</p>}
            <p className="finding-reason">{f.reason}</p>
            {f.effect_on_intended_use && !f.accepted && <p className="finding-remedy"><span>Why it matters here:</span> {f.effect_on_intended_use}</p>}
            {f.remedy && <p className="finding-remedy"><span>To fix:</span> {f.remedy}</p>}
            {f.reconsider && <p className="finding-remedy"><span>Evidence that would change this:</span> {f.reconsider}</p>}
            <Evidence f={f} />
          </li>
        ))}
      </ul>
      {csv && (
        <div className="cert-actions" style={{ marginTop: 16 }}>
          <button type="button" className="secondary" onClick={download}>Download findings (event template CSV)</button>
        </div>
      )}
    </section>
  );
}
