import { VERDICT_COPY, type Finding } from "@/lib/types";

export function Findings({ findings }: { findings: Finding[] }) {
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
              <span className="finding-level">{VERDICT_COPY[f.verdict].label}{f.accepted ? " · accepted by the question card" : ""}</span>
            </div>
            {f.accepted && <p className="finding-remedy"><span>Accepted as:</span> {f.accepted_as}. Still shown so a reviewer can confirm it.</p>}
            <p className="finding-reason">{f.reason}</p>
            {f.remedy && <p className="finding-remedy"><span>To fix:</span> {f.remedy}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
