import { VERDICT_COPY, VERDICT_ORDER, type CheckResult, type Finding } from "@/lib/types";

const NAMES: Record<string, string> = {
  metadata: "Documentation and license",
  scope: "Permitted use",
  spec_quality: "Question clarity",
  columns: "Required columns",
  cohort: "Target population",
  completeness: "Missing values",
  outcome_events: "Enough outcome events",
  leakage: "Outcome leakage",
  temporal: "Follow-up length",
  units: "Patients counted once",
  consistency: "Records agree across sources",
  plausibility: "Plausible values",
  subgroups: "Subgroup coverage",
  phi: "Direct identifiers",
  injection: "Embedded instructions",
};

function statusOf(c: CheckResult, findings: Finding[]) {
  if (c.status === "skipped") return { text: "Not applicable", key: "na" };
  if (c.status === "not_evaluable") return { text: "Could not run", key: "warn" };
  const own = findings.filter((f) => f.check === c.check);
  if (own.length === 0) return { text: "Passed", key: "pass" };
  if (own.every((f) => f.accepted)) return { text: "Accepted by the card", key: "accepted" };
  const worst = own.reduce((a, f) =>
    VERDICT_ORDER.indexOf(f.verdict) > VERDICT_ORDER.indexOf(a) ? f.verdict : a, own[0].verdict);
  return { text: VERDICT_COPY[worst].label, key: worst };
}

export function ChecksTable({ checks, findings }: { checks: CheckResult[]; findings: Finding[] }) {
  if (checks.length === 0) return null;
  return (
    <section aria-label="All checks">
      <div className="table-scroll">
        <table className="checks">
          <thead>
            <tr><th scope="col">Check</th><th scope="col">Result</th></tr>
          </thead>
          <tbody>
            {checks.map((c) => {
              const s = statusOf(c, findings);
              return (
                <tr key={c.check}>
                  <th scope="row">{NAMES[c.check] ?? c.check}</th>
                  <td><span className="status" data-status={s.key}>{s.text}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
