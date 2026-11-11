import { VERDICT_COPY, VERDICT_ORDER, type Verdict } from "@/lib/types";

/** The verdict shown on the full four-step scale, so the reader sees where it sits. */
export function VerdictGate({ verdict, question, line }: { verdict: Verdict; question?: string; line?: string }) {
  const copy = { ...VERDICT_COPY[verdict], ...(line ? { line } : {}) };
  return (
    <section className="gate" aria-labelledby="verdict-heading" data-verdict={verdict}>
      {question && <blockquote className="gate-question">{question}</blockquote>}
      <ol className="gate-scale" aria-label="Possible verdicts">
        {VERDICT_ORDER.map((v) => (
          <li key={v} className="gate-step" data-step={v} aria-current={v === verdict ? "true" : undefined}>
            {VERDICT_COPY[v].label}
          </li>
        ))}
      </ol>
      <h2 id="verdict-heading" className="gate-verdict">{copy.label}</h2>
      <p className="gate-line">{copy.line}</p>
    </section>
  );
}
