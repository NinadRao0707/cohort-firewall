"use client";
import { useEffect, useRef, useState } from "react";
import { InputPanel, type Submission } from "@/components/InputPanel";
import { Results } from "@/components/Results";
import { evaluate, loadSample } from "@/lib/api";
import type { EvaluateResponse } from "@/lib/types";

export default function Home() {
  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const outputRef = useRef<HTMLElement>(null);

  // On narrow screens the result renders below the form; bring it into view.
  useEffect(() => {
    if ((result || error) && window.matchMedia("(max-width: 860px)").matches) {
      outputRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result, error]);

  async function run(task: () => Promise<EvaluateResponse>) {
    setBusy(true);
    setError("");
    try {
      setResult(await task());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(s: Submission) {
    run(() => evaluate({
      dataset: s.dataset,
      dictionary: s.dictionary,
      spec: s.mode === "spec" ? s.text : undefined,
      question: s.mode === "question" ? s.text : undefined,
    }));
  }

  return (
    <main className="shell">
      <header className="masthead">
        <h1>Cohort Firewall</h1>
        <p>Check whether an oncology dataset can answer your AI question before anyone trains on it.</p>
      </header>
      <div className="layout">
        <InputPanel busy={busy} onSubmit={onSubmit} onSample={(n) => run(() => loadSample(n))} />
        <section className="output" aria-live="polite" ref={outputRef}>
          {error && <p className="error" role="alert">{error}</p>}
          {result ? <Results result={result} /> : (
            <div className="empty">
              <p>Upload a dataset and describe the question, or open a sample result.</p>
              <p className="quiet">
                Rules decide the verdict. The language model only helps read your question and explain the result.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
