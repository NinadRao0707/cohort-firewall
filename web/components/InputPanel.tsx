"use client";
import { useState } from "react";
import { apiConfigured, SAMPLES } from "@/lib/api";

export interface Submission {
  dataset: File;
  dictionary: File | null;
  mode: "question" | "spec";
  text: string;
}

export function InputPanel({ busy, onSubmit, onSample }: {
  busy: boolean;
  onSubmit: (s: Submission) => void;
  onSample: (name: string) => void;
}) {
  const [dataset, setDataset] = useState<File | null>(null);
  const [dictionary, setDictionary] = useState<File | null>(null);
  const [mode, setMode] = useState<"question" | "spec">("question");
  const [text, setText] = useState("");

  const ready = apiConfigured && dataset && text.trim().length > 0 && !busy;

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (dataset) onSubmit({ dataset, dictionary, mode, text });
        }}
      >
        <label className="field">
          <span>Dataset (CSV)</span>
          <input type="file" accept=".csv,text/csv" onChange={(e) => setDataset(e.target.files?.[0] ?? null)} />
        </label>
        <label className="field">
          <span>Data dictionary (JSON)</span>
          <input type="file" accept=".json,application/json"
                 onChange={(e) => setDictionary(e.target.files?.[0] ?? null)} />
          <small>Without one, the result is Insufficient evidence.</small>
        </label>

        <fieldset className="field">
          <legend>Proposed AI question</legend>
          <div className="toggle" role="radiogroup">
            <label><input type="radio" name="mode" checked={mode === "question"}
                          onChange={() => setMode("question")} /> Plain language</label>
            <label><input type="radio" name="mode" checked={mode === "spec"}
                          onChange={() => setMode("spec")} /> Question spec (JSON)</label>
          </div>
          <textarea rows={mode === "spec" ? 10 : 5} value={text} onChange={(e) => setText(e.target.value)}
                    placeholder={mode === "question"
                      ? "Can we model 2-year recurrence in stage I–III breast cancer from receptor status and stage?"
                      : '{ "question_text": "...", "task_type": "binary_classification", ... }'} />
        </fieldset>

        <button type="submit" disabled={!ready}>{busy ? "Checking…" : "Check readiness"}</button>
        {!apiConfigured && <p className="quiet">The API isn't connected. Try a sample result instead.</p>}
      </form>

      <div className="samples">
        <h3>Sample results</h3>
        <p className="quiet">TCGA-BRCA (judged data) first, then stand-in and Synthea test cohorts.</p>
        <ul>
          {SAMPLES.map((s) => (
            <li key={s.name}>
              <button type="button" className="link" onClick={() => onSample(s.name)}>{s.label}</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
