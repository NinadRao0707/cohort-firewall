import type { EvaluateResponse } from "@/lib/types";

/** Which samples can answer the question: who is left after each step. */
export function Funnel({ funnel, name }: { funnel: EvaluateResponse["funnel"]; name?: string }) {
  if (!funnel || !funnel.steps.length) return null;
  const top = funnel.steps[0].n || 1;
  function download() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([funnel!.samples_csv], { type: "text/csv" }));
    a.download = `cohort_samples-${name ?? "result"}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  return (
    <section aria-label="Which samples can answer it">
      <p className="quiet tab-intro">Records left after each condition and each field the question needs.</p>
      <ol className="funnel">
        {funnel.steps.map((s, i) => (
          <li key={i}>
            <div className="funnel-label">
              <span>{s.step}</span>
              <span className="funnel-n">{s.n.toLocaleString()}{s.dropped ? <span className="quiet"> (−{s.dropped.toLocaleString()})</span> : null}</span>
            </div>
            <div className="funnel-bar" aria-hidden="true"><span style={{ width: `${Math.max(1, (100 * s.n) / top)}%` }} /></div>
          </li>
        ))}
      </ol>
      <p className="funnel-final">
        <strong>{funnel.n_final.toLocaleString()} records</strong>
        {funnel.n_patients_final !== null ? ` from ${funnel.n_patients_final.toLocaleString()} patients` : ""}
        {funnel.not_in_data.length
          ? ` have every field this dataset holds for the question, but none can supply ${funnel.not_in_data.join(", ")}, so no record can answer it exactly as asked.`
          : " can answer the question exactly as asked."}
        {funnel.repeated_patients ? ` ${funnel.repeated_patients} are extra samples from patients already counted.` : ""}
      </p>
      <details className="fold"><summary>How this is counted</summary><p className="quiet">{funnel.note}</p></details>
      <div className="actions"><button type="button" className="secondary" onClick={download}>Download sample list (CSV)</button></div>
    </section>
  );
}
