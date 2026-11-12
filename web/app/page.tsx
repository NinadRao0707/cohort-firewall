"use client";
import { useEffect, useRef, useState } from "react";
import { InputPanel, type Submission } from "@/components/InputPanel";
import { Nav } from "@/components/Nav";
import { ChipPopover } from "@/components/Popover";
import { QuestionCard } from "@/components/QuestionCard";
import { Results } from "@/components/Results";
import { apiConfigured, evaluate, loadSample } from "@/lib/api";
import { evaluateCard } from "@/lib/card";
import type { EvaluateResponse } from "@/lib/types";

export default function Home() {
  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const out = useRef<HTMLElement>(null);
  useEffect(() => { if (result || error) out.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [result, error]);

  async function run(task: () => Promise<EvaluateResponse>) {
    setBusy(true); setError("");
    try { setResult(await task()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  function onUpload(s: Submission) {
    run(() => evaluate({ dataset: s.dataset, dictionary: s.dictionary,
      spec: s.mode === "spec" ? s.text : undefined, question: s.mode === "question" ? s.text : undefined }));
  }

  return (
    <main className="shell">
      <header className="masthead">
        <h1>Cohort Firewall</h1>
        <p>Can this data answer your research question?</p>
      </header>
      <Nav current="question" />
      <section className="toolbar" aria-label="Question">
        {apiConfigured ? <QuestionCard busy={busy} onSubmit={(id, spec) => run(() => evaluateCard(id, spec))} />
          : <p className="quiet">The API isn&apos;t running, so only saved results can be opened.</p>}
        <div className="toolbar-foot">
          <ChipPopover variant="plain" title="Other ways to check" label="Upload files or open a saved result" width={380}>
            {() => <InputPanel busy={busy} onSubmit={onUpload} onSample={(n) => run(() => loadSample(n))} />}
          </ChipPopover>
        </div>
      </section>
      <section className="output" aria-live="polite" ref={out}>
        {error && <p className="error" role="alert">{error}</p>}
        {result ? <Results result={result} /> : (
          <div className="empty">
            <p>Pick an example, or describe your question and set the filters, then select Check readiness.</p>
            <p className="quiet">You&apos;ll get one of four answers, Ready, Conditional, Blocked or Insufficient evidence, with the reasons.</p>
          </div>
        )}
      </section>
      <footer className="disclaimer">Research data-readiness tool. Not for diagnosis, treatment or patient risk scores.</footer>
    </main>
  );
}
