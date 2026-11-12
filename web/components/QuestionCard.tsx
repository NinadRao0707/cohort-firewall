"use client";
import { useEffect, useMemo, useState } from "react";
import {
  describeDataset, exampleCards, getAcceptable, listDatasets,
  type Acceptable, type ColumnInfo, type DatasetInfo, type Spec,
} from "@/lib/card";

const USES: { value: Spec["intended_use"]; label: string }[] = [
  { value: "research", label: "Research analysis" },
  { value: "model_development", label: "Develop a research model" },
  { value: "clinical_decision_support", label: "Support a clinical decision (out of scope)" },
  { value: "direct_patient_care", label: "Direct patient care (out of scope)" },
];
const TASKS: { value: Spec["task_type"]; label: string }[] = [
  { value: "binary_classification", label: "Yes/no outcome within a time horizon" },
  { value: "survival", label: "Time until an event" },
  { value: "descriptive", label: "Describe or compare groups" },
];
const OPS = [
  { value: "==", label: "is" }, { value: "!=", label: "is not" }, { value: "in", label: "is one of" },
  { value: ">=", label: "at least" }, { value: "<=", label: "at most" },
];

interface Filter { column: string; op: string; value: string; values: string[] }

const EMPTY: Spec = {
  question_text: "", task_type: "binary_classification", intended_use: "research",
  population_filters: [], outcome_column: "", outcome_positive_value: 1, time_column: "",
  time_horizon_months: 24, feature_columns: [], subgroup_columns: [], acceptable_limitations: [],
};

export function QuestionCard({ busy, onSubmit }: { busy: boolean; onSubmit: (datasetId: string, spec: Spec) => void }) {
  const [datasets, setDatasets] = useState<{ id: string; label: string }[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [acceptable, setAcceptable] = useState<Acceptable[]>([]);
  const [examples, setExamples] = useState<{ id: string; spec: Spec }[]>([]);
  const [spec, setSpec] = useState<Spec>(EMPTY);
  const [filters, setFilters] = useState<Filter[]>([]);
  const [extra, setExtra] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listDatasets().then((d) => { setDatasets(d); if (d.length) setDatasetId(d[0].id); }).catch((e) => setError(e.message));
    getAcceptable().then(setAcceptable).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!datasetId) return;
    describeDataset(datasetId).then(setInfo).catch((e) => setError(e.message));
    exampleCards(datasetId).then(setExamples).catch(() => setExamples([]));
  }, [datasetId]);

  const col = useMemo(() => Object.fromEntries((info?.columns ?? []).map((c) => [c.name, c])), [info]);
  const by = (roles: string[]) => (info?.columns ?? []).filter((c) => roles.includes(c.role ?? ""));
  const outcomes = by(["outcome"]);
  const times = by(["time"]);
  const predictors = by(["feature", "demographic", "availability"]);
  const groupable = (info?.columns ?? []).filter((c) => c.values && !["id", "patient_id", "outcome"].includes(c.role ?? ""));
  const needsOutcome = spec.task_type !== "descriptive";

  function set<K extends keyof Spec>(k: K, v: Spec[K]) { setSpec((s) => ({ ...s, [k]: v })); }
  function toggle(k: "feature_columns" | "subgroup_columns" | "acceptable_limitations", v: string) {
    setSpec((s) => ({ ...s, [k]: s[k].includes(v) ? s[k].filter((x) => x !== v) : [...s[k], v] }));
  }

  function loadExample(id: string) {
    const ex = examples.find((e) => e.id === id);
    if (!ex) return;
    const s = ex.spec;
    setSpec({ ...EMPTY, ...s, acceptable_limitations: s.acceptable_limitations ?? [] });
    setFilters((s.population_filters ?? []).map((f) => ({
      column: f.column, op: f.op,
      value: Array.isArray(f.value) ? "" : String(f.value),
      values: Array.isArray(f.value) ? f.value.map(String) : [],
    })));
  }

  function cast(c: ColumnInfo | undefined, v: string): unknown {
    const isNum = c && (c.min !== undefined || (c.values ?? []).every((x) => typeof x.value === "number"));
    return isNum && v !== "" && !Number.isNaN(Number(v)) ? Number(v) : v;
  }

  function submit() {
    setError("");
    if (!spec.question_text.trim()) return setError("Describe the research question in words.");
    if (needsOutcome && !spec.outcome_column) return setError("Choose the outcome of interest.");
    const population_filters = filters.filter((f) => f.column).map((f) => ({
      column: f.column, op: f.op,
      value: f.op === "in" ? f.values.map((v) => cast(col[f.column], v)) : cast(col[f.column], f.value),
    }));
    onSubmit(datasetId, {
      ...spec, population_filters,
      outcome_column: needsOutcome ? spec.outcome_column : null,
      time_column: spec.time_column || null,
      time_horizon_months: spec.time_horizon_months ? Number(spec.time_horizon_months) : null,
      parse_confidence: 1,
    });
  }

  return (
    <form className="card-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <label className="field">
        <span>Dataset</span>
        <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
          {datasets.length === 0 && <option value="">No server datasets (run data/flatten_tcga.py)</option>}
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
        {info && <small>{info.n_rows} rows · {info.columns.length} documented columns</small>}
      </label>

      {examples.length > 0 && (
        <label className="field">
          <span>Start from an example card</span>
          <select defaultValue="" onChange={(e) => loadExample(e.target.value)}>
            <option value="" disabled>Choose an example…</option>
            {examples.map((e) => <option key={e.id} value={e.id}>{e.spec.question_text.slice(0, 80)}…</option>)}
          </select>
        </label>
      )}

      <fieldset className="field">
        <legend>Research question</legend>
        <textarea rows={3} value={spec.question_text} onChange={(e) => set("question_text", e.target.value)}
                  placeholder="Is this dataset suitable for studying …" />
      </fieldset>

      <fieldset className="field">
        <legend>Intended use</legend>
        {USES.map((u) => (
          <label key={u.value} className="choice">
            <input type="radio" name="use" checked={spec.intended_use === u.value} onChange={() => set("intended_use", u.value)} /> {u.label}
          </label>
        ))}
      </fieldset>

      <fieldset className="field">
        <legend>Group being studied</legend>
        {filters.map((f, i) => {
          const c = col[f.column];
          const upd = (p: Partial<Filter>) => setFilters((fs) => fs.map((x, j) => (j === i ? { ...x, ...p } : x)));
          return (
            <div key={i} className="filter-row">
              <select value={f.column} onChange={(e) => upd({ column: e.target.value, value: "", values: [] })} aria-label="Column">
                <option value="">Column…</option>
                {(info?.columns ?? []).filter((x) => !["id", "patient_id"].includes(x.role ?? "")).map((x) =>
                  <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
              <select value={f.op} onChange={(e) => upd({ op: e.target.value })} aria-label="Condition">
                {OPS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {f.op === "in" && c?.values ? (
                <div className="chips">
                  {c.values.map((v) => (
                    <label key={String(v.value)} className="chip">
                      <input type="checkbox" checked={f.values.includes(String(v.value))}
                             onChange={() => upd({ values: f.values.includes(String(v.value)) ? f.values.filter((x) => x !== String(v.value)) : [...f.values, String(v.value)] })} />
                      {String(v.value)}
                    </label>
                  ))}
                </div>
              ) : c?.values ? (
                <select value={f.value} onChange={(e) => upd({ value: e.target.value })} aria-label="Value">
                  <option value="">Value…</option>
                  {c.values.map((v) => <option key={String(v.value)} value={String(v.value)}>{String(v.value)} ({v.n})</option>)}
                </select>
              ) : (
                <input type="number" value={f.value} onChange={(e) => upd({ value: e.target.value })} aria-label="Value"
                       placeholder={c ? `${c.min ?? ""} to ${c.max ?? ""}` : ""} />
              )}
              <button type="button" className="link" onClick={() => setFilters((fs) => fs.filter((_, j) => j !== i))}>Remove</button>
            </div>
          );
        })}
        <button type="button" className="link" onClick={() => setFilters((fs) => [...fs, { column: "", op: "==", value: "", values: [] }])}>
          + Add a condition
        </button>
      </fieldset>

      <fieldset className="field">
        <legend>Outcome of interest</legend>
        <select value={spec.task_type} onChange={(e) => set("task_type", e.target.value as Spec["task_type"])} aria-label="Kind of question">
          {TASKS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        {needsOutcome && (
          <select value={spec.outcome_column ?? ""} onChange={(e) => set("outcome_column", e.target.value)} aria-label="Outcome column">
            <option value="">Outcome column…</option>
            {outcomes.map((c) => <option key={c.name} value={c.name}>{c.name}: {c.description}</option>)}
          </select>
        )}
        <div className="filter-row">
          <select value={spec.time_column ?? ""} onChange={(e) => set("time_column", e.target.value)} aria-label="Follow-up time column">
            <option value="">Follow-up time column (optional)…</option>
            {times.map((c) => <option key={c.name} value={c.name}>{c.name}{c.unit ? ` (${c.unit})` : ""}</option>)}
          </select>
          <label className="inline">Horizon <input type="number" min={1} value={spec.time_horizon_months ?? ""}
                 onChange={(e) => set("time_horizon_months", e.target.value ? Number(e.target.value) : null)} /> months</label>
        </div>
      </fieldset>

      <fieldset className="field">
        <legend>Predictors to use</legend>
        <div className="chips">
          {predictors.map((c) => (
            <label key={c.name} className="chip" title={c.description}>
              <input type="checkbox" checked={spec.feature_columns.includes(c.name)} onChange={() => toggle("feature_columns", c.name)} /> {c.name}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="field">
        <legend>Check fairness across</legend>
        <div className="chips">
          {groupable.filter((c) => c.role === "demographic" || c.role === "feature").map((c) => (
            <label key={c.name} className="chip">
              <input type="checkbox" checked={spec.subgroup_columns.includes(c.name)} onChange={() => toggle("subgroup_columns", c.name)} /> {c.name}
            </label>
          ))}
          {spec.subgroup_columns.filter((s) => !col[s]).map((s) => (
            <label key={s} className="chip missing"><input type="checkbox" checked onChange={() => toggle("subgroup_columns", s)} /> {s} (not in data)</label>
          ))}
        </div>
        <div className="filter-row">
          <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Attribute not in this dataset, e.g. race" aria-label="Other attribute" />
          <button type="button" className="secondary" onClick={() => { if (extra.trim()) { toggle("subgroup_columns", extra.trim()); setExtra(""); } }}>Add</button>
        </div>
      </fieldset>

      <fieldset className="field">
        <legend>Acceptable limitations for this use</legend>
        <small>Accepted limitations stay visible in the result and the record, but don&apos;t lower the verdict. Blocked problems can never be accepted.</small>
        {acceptable.map((a) => (
          <label key={a.rule_id} className="choice">
            <input type="checkbox" checked={spec.acceptable_limitations.includes(a.rule_id)} onChange={() => toggle("acceptable_limitations", a.rule_id)} />
            {" "}{a.label} <span className="quiet">({a.rule_id})</span>
          </label>
        ))}
      </fieldset>

      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy || !info}>{busy ? "Checking…" : "Check readiness"}</button>
    </form>
  );
}
