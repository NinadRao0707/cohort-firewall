import type { QuestionStep } from "@/lib/types";

type TowerStep = { rank: number; action: string; samples: string[]; n_samples: number; resolves: string[]; affects_analyses: string[] };

/** Plain-English result and the next steps, most serious first. */
export function Summary({ text, steps }: { text?: string; steps?: (QuestionStep | TowerStep)[] }) {
  if (!text) return null;
  return (
    <section className="block summary" aria-labelledby="sum-h">
      <h3 id="sum-h">In plain terms</h3>
      <p className="summary-text">{text}</p>
      {steps && steps.length > 0 && (
        <>
          <h3>Next steps, most important first</h3>
          <ol className="steps">
            {steps.map((s) => "rule_id" in s ? (
              <li key={s.rank}>
                <strong>{s.action}</strong>
                <span className="quiet"> {s.size ? `Affects ${s.size}. ` : ""}Resolves {s.rule_id}
                  {s.unblocks ? " (needed before this can pass)" : ""}.</span>
                {s.evidence_to_reconsider && <span className="quiet"> To reconsider: {s.evidence_to_reconsider}</span>}
              </li>
            ) : (
              <li key={s.rank}>
                <strong>{s.action}</strong>
                <span className="quiet"> Resolves {s.resolves.join(", ")}{s.affects_analyses.length ? `; needed before ${s.affects_analyses.join(", ")} can be used` : ""}.</span>
                {s.samples.length > 0 && <span className="quiet"> <code>{s.samples.slice(0, 6).join(", ")}{s.n_samples > 6 ? ` +${s.n_samples - 6}` : ""}</code></span>}
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
