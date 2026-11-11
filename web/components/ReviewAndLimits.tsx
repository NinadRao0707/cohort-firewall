import type { EvaluateResponse } from "@/lib/types";

/** Who must look at this result, what the engine adjusted, and what the tool cannot tell you. */
export function HumanReview({ review }: { review: EvaluateResponse["human_review"] }) {
  if (!review) return null;
  return (
    <p className="review" data-level={review.level}>
      <span>Human review {review.level}.</span> {review.text}
    </p>
  );
}

export function NotesAndLimits({ notes, limitations }: { notes?: string[]; limitations?: string[] }) {
  if (!notes?.length && !limitations?.length) return null;
  return (
    <section className="block">
      {notes && notes.length > 0 && (
        <>
          <h3>Data notes</h3>
          <ul className="plain-list">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
      {limitations && limitations.length > 0 && (
        <details className="limits">
          <summary>Limitations of this check</summary>
          <ul className="plain-list">{limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </details>
      )}
    </section>
  );
}
