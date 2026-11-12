"use client";
import { useEffect, useRef, useState } from "react";
import { InputPanel, type Submission } from "@/components/InputPanel";
import { QuestionCard } from "@/components/QuestionCard";
import { evaluateCard } from "@/lib/card";
import { apiConfigured } from "@/lib/api";
import { Nav } from "@/components/Nav";
import { Results } from "@/components/Results";
import { evaluate, loadSample } from "@/lib/api";
import type { EvaluateResponse } from "@/lib/types";

export default function Home() {
  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"card" | "upload">(apiConfigured ? "card" : "upload");
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
        <p>Check whether the data can answer your research question before anyone uses it.</p>
      </header>
      <Nav current="question" />
      <div className="layout">
        <aside className="panel">
          <div className="toggle" role="radiogroup" aria-label="Input">
            <label><input type="radio" checked={mode === "card"} disabled={!apiConfigured} onChange={() => setMode("card")} /> Fill in a question</label>
            <label><input type="radio" checked={mode === "upload"} onChange={() => setMode("upload")} /> Upload files</label>
          </div>
          {mode === "card"
            ? <QuestionCard busy={busy} onSubmit={(id, spec) => run(() => evaluateCard(id, spec))} />
            : <InputPanel busy={busy} onSubmit={onSubmit} onSample={(n) => run(() => loadSample(n))} />}
        </aside>
        <section className="output" aria-live="polite" ref={outputRef}>
          {error && <p className="error" role="alert">{error}</p>}
          {result ? <Results result={result} /> : (
            <div className="empty">
              <p>Fill in the question on the left, or start from an example, then select Check readiness.</p>
              <p className="quiet">Rules decide the verdict, and every result shows why.</p>
            </div>
          )}
        </section>
      </div>
      <footer className="disclaimer">Research data-readiness tool. Not for diagnosis, treatment or patient risk scores.</footer>
    </main>
  );
}
