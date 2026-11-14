"use client";

/** A summary safe to share beyond the review team: counts from 1 to 10 hidden (CMS small-cell rule). */
export function ShareableSummary({ data, name }: { data?: { text: string; note: string }; name: string }) {
  if (!data?.text) return null;
  function download() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([`${data!.text}\n\n${data!.note}\n`], { type: "text/plain" }));
    a.download = `shareable-summary-${name}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  return (
    <section className="block" aria-labelledby="share-h">
      <h3 id="share-h">Shareable summary</h3>
      <p className="quiet">{data.note}</p>
      <details className="fold"><summary>Preview</summary><p className="quiet">{data.text}</p></details>
      <div className="actions"><button type="button" className="secondary" onClick={download}>Download shareable summary</button></div>
    </section>
  );
}
