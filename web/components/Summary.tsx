import type { QuestionStep } from "@/lib/types";

type TowerStep = { rank: number; action: string; samples: string[]; n_samples: number; resolves: string[];
                   affects_analyses: string[]; evidence_to_reconsider?: string };

export function NextSteps({ steps }: { steps?: (QuestionStep | TowerStep)[] }) {
  if (!steps || steps.length === 0) return <p className="quiet">Nothing to fix for this question.</p>;
  return (
    <ol className="steps">
      {steps.map((s) => "rule_id" in s ? (
        <li key={s.rank}>
          <strong>{s.action}</strong>
          <span className="quiet">{s.size ? `Affects ${s.size}. ` : ""}Resolves {s.rule_id}{s.unblocks ? ", needed before this can pass" : ""}.</span>
        </li>
      ) : (
        <li key={s.rank}>
          <strong>{s.action}</strong>
          <span className="quiet">Resolves {s.resolves.join(", ")}{s.affects_analyses.length ? `; needed before ${s.affects_analyses.join(", ")} can be used` : ""}.</span>
          {s.evidence_to_reconsider && <span className="quiet">What would change the verdict: {s.evidence_to_reconsider.replace(/^Reconsider once /, "once ")}</span>}
        </li>
      ))}
    </ol>
  );
}
