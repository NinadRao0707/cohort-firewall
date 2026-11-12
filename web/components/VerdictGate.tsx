import { VERDICT_COPY, VERDICT_ORDER, type Verdict } from "@/lib/types";

/** The verdict on its four-step scale, with the plain-English answer underneath. */
export function VerdictGate({ verdict, question, line, summary, review }: {
  verdict: Verdict; question?: string; line?: string; summary?: string; review?: { level: string; text: string };
}) {
  const copy = VERDICT_COPY[verdict];
  return (
    <section className="gate" aria-labelledby="verdict-heading" data-verdict={verdict}>
      {question && <p className="gate-question">{question}</p>}
      <ol className="gate-scale" aria-label="Possible verdicts">
        {VERDICT_ORDER.map((v) => (
          <li key={v} className="gate-step" aria-current={v === verdict ? "true" : undefined}>{VERDICT_COPY[v].label}</li>
        ))}
      </ol>
      <h2 id="verdict-heading" className="gate-verdict">{copy.label}</h2>
      <p className="gate-line">{line ?? copy.line}</p>
      {summary && <p className="gate-summary">{summary}</p>}
      {review && <p className="review-pill" data-level={review.level}>Human review {review.level}</p>}
    </section>
  );
}
