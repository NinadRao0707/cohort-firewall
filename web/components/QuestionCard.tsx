"use client";
import { useEffect, useMemo, useState } from "react";
import {
  describeDataset, exampleCards, getAcceptable, listDatasets,
  type Acceptable, type ColumnInfo, type DatasetInfo, type Spec,
} from "@/lib/card";
import { CheckList, ChipPopover } from "./Popover";

const USES: { value: Spec["intended_use"]; label: string; short: string; hint: string }[] = [
  { value: "research", label: "Research analysis", short: "Research", hint: "Describe, compare or study the cohort." },
  { value: "model_development", label: "Develop a research model", short: "Research model", hint: "Train or evaluate a model for research." },
  { value: "clinical_decision_support", label: "Support a clinical decision", short: "Clinical decision", hint: "Out of scope: always Blocked." },
  { value: "direct_patient_care", label: "Direct patient care", short: "Patient care", hint: "Out of scope: always Blocked." },
];
const KINDS: { value: Spec["task_type"]; label: string }[] = [
  { value: "binary_classification", label: "Yes/no outcome within a time" },
  { value: "survival", label: "Time until an event" },
  { value: "descriptive", label: "Describe or compare groups" },
];
type Cond = { column: string; op: string; value: unknown };
const EMPTY: Spec = {
  question_text: "", task_type: "descriptive", intended_use: "research", population_filters: [],
  outcome_column: "", outcome_positive_value: 1, time_column: "", time_horizon_months: null,
  feature_columns: [], subgroup_columns: [], acceptable_limitations: [],
};
const pretty = (s: string) => s.replace(/_/g, " ");
const list = (xs: string[], none: string) => xs.length === 0 ? none
  : xs.length <= 2 ? xs.map(pretty).join(", ") : `${pretty(xs[0])} +${xs.length - 1}`;

function condText(c: Cond) {
  const v = Array.isArray(c.value) ? c.value.join(" or ") : String(c.value);
  const op = c.op === ">=" ? "at least " : c.op === "<=" ? "at most " : c.op === "!=" ? "not " : "";
  return `${pretty(c.column)}: ${op}${v}`;
}

function ConditionEditor({ columns, initial, onSave }: { columns: ColumnInfo[]; initial?: Cond; onSave: (c: Cond) => void }) {
  const [col, setCol] = useState(initial?.column ?? "");
  const [q, setQ] = useState("");
  const info = columns.find((c) => c.name === col);
  const [vals, setVals] = useState<string[]>(Array.isArray(initial?.value) ? (initial!.value as unknown[]).map(String)
    : initial && initial.op === "==" ? [String(initial.value)] : []);
  const [min, setMin] = useState(initial?.op === ">=" ? String(initial.value) : "");
  const [max, setMax] = useState(initial?.op === "<=" ? String(initial.value) : "");
  if (!info) {
    const shown = columns.filter((c) => !q || c.name.toLowerCase().includes(q.toLowerCase()));
    return (
      <div className="checklist">
        <input type="search" placeholder="Search fields" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search fields" />
        <ul>{shown.map((c) => (
          <li key={c.name}><button type="button" className="row-btn" onClick={() => setCol(c.name)}>
            <span className="cl-label">{pretty(c.name)}</span><span className="cl-hint">{c.description}</span></button></li>
        ))}</ul>
      </div>
    );
  }
  const numeric = info.values === undefined;
  const cast = (v: string) => (typeof info.values?.[0]?.value === "number" ? Number(v) : v);
  return (
    <div className="editor">
      <button type="button" className="link" onClick={() => setCol("")}>Change field</button>
      <p className="editor-field">{pretty(info.name)}</p>
      {numeric ? (
        <div className="range">
          <label>At least<input type="number" value={min} onChange={(e) => setMin(e.target.value)} placeholder={String(info.min ?? "")} /></label>
          <label>At most<input type="number" value={max} onChange={(e) => setMax(e.target.value)} placeholder={String(info.max ?? "")} /></label>
        </div>
      ) : (
        <CheckList items={(info.values ?? []).map((v) => ({ value: String(v.value), label: String(v.value), hint: `${v.n} records` }))}
                   selected={vals} onToggle={(v) => setVals((s) => s.includes(v) ? s.filter((x) => x !== v) : [...s, v])} />
      )}
      <button type="button" disabled={numeric ? !(min || max) : vals.length === 0} onClick={() => {
        if (numeric) onSave(min ? { column: info.name, op: ">=", value: Number(min) } : { column: info.name, op: "<=", value: Number(max) });
        else onSave(vals.length === 1 ? { column: info.name, op: "==", value: cast(vals[0]) }
          : { column: info.name, op: "in", value: vals.map(cast) });
      }}>Apply</button>
    </div>
  );
}

export function QuestionCard({ busy, onSubmit }: { busy: boolean; onSubmit: (datasetId: string, spec: Spec) => void }) {
  const [datasets, setDatasets] = useState<{ id: string; label: string }[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [acceptable, setAcceptable] = useState<Acceptable[]>([]);
  const [examples, setExamples] = useState<{ id: string; spec: Spec & { title?: string } }[]>([]);
  const [spec, setSpec] = useState<Spec>(EMPTY);
  const [conds, setConds] = useState<Cond[]>([]);
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

  const cols = info?.columns ?? [];
  const col = useMemo(() => Object.fromEntries(cols.map((c) => [c.name, c])), [cols]);
  const by = (roles: string[]) => cols.filter((c) => roles.includes(c.role ?? ""));
  const filterable = cols.filter((c) => !["id", "patient_id"].includes(c.role ?? ""));
  const predictors = by(["feature", "demographic", "availability"]);
  const groupable = cols.filter((c) => c.values && ["feature", "demographic"].includes(c.role ?? ""));
  const needsOutcome = spec.task_type !== "descriptive";
  const set = <K extends keyof Spec>(k: K, v: Spec[K]) => setSpec((s) => ({ ...s, [k]: v }));
  const toggle = (k: "feature_columns" | "subgroup_columns" | "acceptable_limitations", v: string) =>
    setSpec((s) => ({ ...s, [k]: s[k].includes(v) ? s[k].filter((x) => x !== v) : [...s[k], v] }));
  const use = USES.find((u) => u.value === spec.intended_use)!;

  function loadExample(id: string) {
    const ex = examples.find((e) => e.id === id);
    if (!ex) return;
    const s = ex.spec;
    setSpec({ ...EMPTY, ...s, outcome_column: s.outcome_column ?? "", time_column: s.time_column ?? "",
              time_horizon_months: s.time_horizon_months ?? null, acceptable_limitations: s.acceptable_limitations ?? [] });
    setConds((s.population_filters ?? []) as Cond[]);
    setError("");
  }
  function clearAll() { setSpec({ ...EMPTY, question_text: spec.question_text }); setConds([]); }
  function submit() {
    setError("");
    if (!spec.question_text.trim()) return setError("Write the question in one sentence.");
    if (needsOutcome && !spec.outcome_column) return setError("Choose an outcome, or set Outcome to Describe or compare groups.");
    onSubmit(datasetId, { ...spec, population_filters: conds,
      outcome_column: needsOutcome ? spec.outcome_column : null,
      time_column: needsOutcome ? spec.time_column || null : null,
      time_horizon_months: needsOutcome && spec.time_horizon_months ? Number(spec.time_horizon_months) : null,
      parse_confidence: 1 });
  }
  const outcomeLabel = !needsOutcome ? "none, describe groups"
    : `${spec.outcome_column ? pretty(spec.outcome_column) : "choose…"}${spec.time_horizon_months ? ` within ${spec.time_horizon_months} mo` : ""}`;
  const active = conds.length + spec.feature_columns.length + spec.subgroup_columns.length + spec.acceptable_limitations.length;

  return (
    <form className="qbar" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div className="qbar-top">
        <label className="sr-only" htmlFor="q-text">Research question</label>
        <input id="q-text" className="q-input" value={spec.question_text} onChange={(e) => set("question_text", e.target.value)}
               placeholder="What do you want to find out? For example: is this data suitable for a 5-year survival study?" />
        <ChipPopover title="Start from an example" label="Examples" width={360}>
          {(close) => (
            <ul className="menu">{examples.map((e) => (
              <li key={e.id}><button type="button" className="row-btn" onClick={() => { loadExample(e.id); close(); }}>
                {e.spec.title ?? e.spec.question_text.slice(0, 60)}</button></li>
            ))}{examples.length === 0 && <li className="quiet">No examples for this dataset.</li>}</ul>
          )}
        </ChipPopover>
      </div>

      <div className="chips-row" role="group" aria-label="Question filters">
        <ChipPopover title="Dataset" label={<><span className="k">Data</span> {info?.label.split(",")[0] ?? "…"}</>}>
          {(close) => (
            <ul className="menu">{datasets.map((d) => (
              <li key={d.id}><label className="radio-row"><input type="radio" checked={d.id === datasetId}
                onChange={() => { setDatasetId(d.id); clearAll(); close(); }} /> {d.label}</label></li>
            ))}</ul>
          )}
        </ChipPopover>

        <ChipPopover title="Intended use" label={<><span className="k">Use</span> {use.short}</>}>
          {(close) => (
            <ul className="menu">{USES.map((u) => (
              <li key={u.value}><label className="radio-row"><input type="radio" checked={spec.intended_use === u.value}
                onChange={() => { set("intended_use", u.value); close(); }} />
                <span><span className="cl-label">{u.label}</span><span className="cl-hint">{u.hint}</span></span></label></li>
            ))}</ul>
          )}
        </ChipPopover>

        {conds.map((c, i) => (
          <ChipPopover key={`${c.column}-${i}`} title="Who is studied" label={<><span className="k">Who</span> {condText(c).split(": ")[1]}</>}
                       onRemove={() => setConds((cs) => cs.filter((_, j) => j !== i))}>
            {(close) => <ConditionEditor columns={filterable} initial={c}
              onSave={(n) => { setConds((cs) => cs.map((x, j) => (j === i ? n : x))); close(); }} />}
          </ChipPopover>
        ))}
        <ChipPopover variant="add" title="Who is studied" label="+ Who">
          {(close) => <ConditionEditor columns={filterable} onSave={(n) => { setConds((cs) => [...cs, n]); close(); }} />}
        </ChipPopover>

        <ChipPopover title="Outcome" label={<><span className="k">Outcome</span> {outcomeLabel}</>} width={340}>
          {() => (
            <div className="editor">
              <fieldset><legend>Kind of question</legend>
                {KINDS.map((k) => <label key={k.value} className="radio-row"><input type="radio" checked={spec.task_type === k.value}
                  onChange={() => set("task_type", k.value)} /> {k.label}</label>)}</fieldset>
              {needsOutcome && (<>
                <label className="field"><span>Outcome</span>
                  <select value={spec.outcome_column ?? ""} onChange={(e) => set("outcome_column", e.target.value)}>
                    <option value="">Choose…</option>
                    {by(["outcome"]).map((c) => <option key={c.name} value={c.name}>{pretty(c.name)}</option>)}
                  </select></label>
                <label className="field"><span>Follow-up time</span>
                  <select value={spec.time_column ?? ""} onChange={(e) => set("time_column", e.target.value)}>
                    <option value="">None</option>
                    {by(["time"]).map((c) => <option key={c.name} value={c.name}>{pretty(c.name)}{c.unit ? ` (${c.unit})` : ""}</option>)}
                  </select></label>
                <label className="field"><span>Within (months)</span>
                  <input type="number" min={1} value={spec.time_horizon_months ?? ""}
                         onChange={(e) => set("time_horizon_months", e.target.value ? Number(e.target.value) : null)} /></label>
              </>)}
            </div>
          )}
        </ChipPopover>

        <ChipPopover title="Predictors" label={<><span className="k">Predictors</span> {list(spec.feature_columns, "none")}</>} width={340}>
          {() => (<>
            <CheckList items={predictors.map((c) => ({ value: c.name, label: pretty(c.name), hint: c.description }))}
                       selected={spec.feature_columns} onToggle={(v) => toggle("feature_columns", v)} />
            {spec.feature_columns.length > 0 && <button type="button" className="link" onClick={() => set("feature_columns", [])}>Clear predictors</button>}
          </>)}
        </ChipPopover>

        <ChipPopover title="Check fairness across" label={<><span className="k">Fairness</span> {list(spec.subgroup_columns, "none")}</>} width={340}>
          {() => (<>
            <CheckList items={[...groupable.map((c) => ({ value: c.name, label: pretty(c.name) })),
                               ...spec.subgroup_columns.filter((s) => !col[s]).map((s) => ({ value: s, label: s, hint: "not in this data" }))]}
                       selected={spec.subgroup_columns} onToggle={(v) => toggle("subgroup_columns", v)} />
            <div className="add-row">
              <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Attribute not in this data, e.g. race" aria-label="Other attribute" />
              <button type="button" className="secondary" onClick={() => { if (extra.trim()) { toggle("subgroup_columns", extra.trim()); setExtra(""); } }}>Add</button>
            </div>
          </>)}
        </ChipPopover>

        <ChipPopover title="Acceptable limitations" width={360}
                     label={<><span className="k">Accepts</span> {spec.acceptable_limitations.length ? `${spec.acceptable_limitations.length} limitation${spec.acceptable_limitations.length > 1 ? "s" : ""}` : "none"}</>}>
          {() => (<>
            <p className="quiet pop-note">Accepted limitations stay visible but don&apos;t lower the verdict. Blocked problems can never be accepted.</p>
            <CheckList search={false} items={acceptable.map((a) => ({ value: a.rule_id, label: a.label }))}
                       selected={spec.acceptable_limitations} onToggle={(v) => toggle("acceptable_limitations", v)} />
          </>)}
        </ChipPopover>

        {active > 0 && <button type="button" className="clear-all" onClick={clearAll}>Clear all</button>}
        <button type="submit" className="run" disabled={busy || !info}>{busy ? "Checking…" : "Check readiness"}</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
