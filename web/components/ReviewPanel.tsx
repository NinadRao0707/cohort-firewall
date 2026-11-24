"use client";
import { LocalOnly } from "./LocalOnly";
import { useState } from "react";
import { DECISION_LABEL, DECISIONS_FOR, downloadJson, reviewQuestion, reviewRelease, type ReviewRecord } from "@/lib/card";
import { apiConfigured } from "@/lib/api";
import type { EvaluateResponse } from "@/lib/types";
import type { FindingsDoc } from "@/lib/tower";

function Record({ rec, evidence, name }: { rec: ReviewRecord; evidence: unknown; name: string }) {
  const r = rec.review;
  return (
    <div className="review-record" role="status">
      <p><strong>Review recorded</strong> (id {r.review_id}, signed {rec.alg}) by {r.reviewer.name}
        {r.reviewer.role ? `, ${r.reviewer.role}` : ""} at {new Date(r.created_at).toLocaleString()}.</p>
      {r.decision && <p>Decision: <strong>{DECISION_LABEL[r.decision]}</strong></p>}
      {r.decisions && <ul className="plain-list">{r.decisions.map((d) =>
        <li key={d.analysis}>{d.analysis} ({d.verdict}): <strong>{DECISION_LABEL[d.decision]}</strong></li>)}</ul>}
      {r.note && <p className="quiet">Note: {r.note}</p>}
      <button type="button" className="secondary"
              onClick={() => downloadJson(`evidence-record-${name}-${r.review_id}.json`, { result: evidence, review: rec })}>
        Download evidence record
      </button>
    </div>
  );
}

function Who({ name, role, note, setName, setRole, setNote, noteHint }: {
  name: string; role: string; note: string; noteHint: string;
  setName: (v: string) => void; setRole: (v: string) => void; setNote: (v: string) => void;
}) {
  return (
    <>
      <div className="filter-row">
        <label className="field"><span>Reviewer name</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="field"><span>Role</span><input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. data steward" /></label>
      </div>
      <label className="field"><span>Note</span>
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={noteHint} />
      </label>
    </>
  );
}

export function QuestionReview({ result }: { result: EvaluateResponse }) {
  const verdict = result.verdict;
  const options = DECISIONS_FOR[verdict];
  const [decision, setDecision] = useState(options[0]);
  const [ack, setAck] = useState<string[]>([]);
  const [name, setName] = useState(""); const [role, setRole] = useState(""); const [note, setNote] = useState("");
  const [rec, setRec] = useState<ReviewRecord | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (!apiConfigured) return (
    <LocalOnly title="Review before use">
      A person reviews the evidence and records a decision: approve, approve with conditions, reject, or ask
      for more evidence. Every decision needs a name and a note, Blocked can&apos;t be approved, and the
      review is signed and timestamped. Reviews are signed by the local app, so they aren&apos;t available here.
    </LocalOnly>
  );
  const toggle = (id: string) => setAck((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));

  async function submit() {
    setBusy(true); setError("");
    try { setRec(await reviewQuestion({ result, reviewer: name, role, decision, acknowledged: ack, note })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <section className="block review-step" aria-labelledby="review-h">
      <h3 id="review-h">Review before use</h3>
      <p className="quiet">A person must review the evidence and record a decision before this dataset is used for this question.
        {verdict === "BLOCKED" || verdict === "INSUFFICIENT_EVIDENCE" ? " Approval isn't available for this verdict." : ""}</p>
      {rec ? <Record rec={rec} evidence={result} name={result.certificate.cert_id} /> : (
        <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
          {result.findings.length > 0 && (
            <fieldset className="field">
              <legend>I have reviewed the evidence for</legend>
              {result.findings.length > 1 && (
                <label className="choice"><input type="checkbox" checked={result.findings.every((f) => ack.includes(f.rule_id))}
                  onChange={(e) => setAck(e.target.checked ? result.findings.map((f) => f.rule_id) : [])} /> <strong>All {result.findings.length} findings below</strong></label>
              )}
              {result.findings.map((f) => (
                <label key={f.rule_id} className="choice">
                  <input type="checkbox" checked={ack.includes(f.rule_id)} onChange={() => toggle(f.rule_id)} />
                  {" "}<strong>{f.rule_id}</strong> {f.accepted ? "(accepted by the card) " : ""}{f.reason}
                </label>
              ))}
            </fieldset>
          )}
          <fieldset className="field">
            <legend>Decision</legend>
            {options.map((o) => (
              <label key={o} className="choice"><input type="radio" name="decision" checked={decision === o} onChange={() => setDecision(o)} /> {DECISION_LABEL[o]}</label>
            ))}
          </fieldset>
          <Who {...{ name, role, note, setName, setRole, setNote }}
               noteHint={decision === "approve" ? "Required: what you checked before approving, and any conditions"
                 : "Required: conditions that apply, or the evidence needed to reconsider"} />
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "Recording…" : "Record review"}</button>
        </form>
      )}
    </section>
  );
}

export function ReleaseReview({ doc }: { doc: FindingsDoc }) {
  const analyses = doc.analyses ?? [];
  const [decisions, setDecisions] = useState<Record<string, string>>(
    Object.fromEntries(analyses.map((a) => [a.id, DECISIONS_FOR[a.verdict ?? "Ready"][0]])));
  const [ack, setAck] = useState<string[]>([]);
  const [name, setName] = useState(""); const [role, setRole] = useState(""); const [note, setNote] = useState("");
  const [rec, setRec] = useState<ReviewRecord | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (!analyses.length) return null;
  if (!apiConfigured) return (
    <LocalOnly title="Review before using the new release">
      A person records a decision for each protected analysis (here A1 and A2). Blocked analyses can only be
      rejected or sent back for more evidence, every decision needs a name and a note, and the review is
      signed and timestamped. Reviews are signed by the local app, so they aren&apos;t available here.
    </LocalOnly>
  );
  const affecting = doc.findings.filter((f) => (f.affects_analyses ?? []).length > 0);
  const toggle = (id: string) => setAck((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));

  async function submit() {
    setBusy(true); setError("");
    try { setRec(await reviewRelease({ findings: doc, reviewer: name, role, decisions, acknowledged: ack, note })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <section className="block review-step" aria-labelledby="rreview-h">
      <h3 id="rreview-h">Review before using the new release</h3>
      <p className="quiet">Record a decision for each protected analysis. Blocked analyses can only be rejected or sent back for more evidence.</p>
      {rec ? <Record rec={rec} evidence={doc} name={doc.data.releases[1]?.name ?? "release"} /> : (
        <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
          {affecting.length > 0 && (
            <fieldset className="field">
              <legend>I have reviewed the evidence for</legend>
              <label className="choice"><input type="checkbox" checked={affecting.every((f) => ack.includes(f.id))}
                onChange={(e) => setAck(e.target.checked ? affecting.map((f) => f.id) : [])} /> <strong>All {affecting.length} findings below</strong></label>
              {affecting.map((f) => (
                <label key={f.id} className="choice">
                  <input type="checkbox" checked={ack.includes(f.id)} onChange={() => toggle(f.id)} /> <strong>{f.id}</strong> {f.summary}
                </label>
              ))}
            </fieldset>
          )}
          {analyses.map((a) => (
            <fieldset key={a.id} className="field">
              <legend>{a.id}: {a.verdict}</legend>
              {DECISIONS_FOR[a.verdict ?? "Ready"].map((o) => (
                <label key={o} className="choice">
                  <input type="radio" name={`d-${a.id}`} checked={decisions[a.id] === o}
                         onChange={() => setDecisions((d) => ({ ...d, [a.id]: o }))} /> {DECISION_LABEL[o]}
                </label>
              ))}
            </fieldset>
          ))}
          <Who {...{ name, role, note, setName, setRole, setNote }} noteHint="Required: what you checked, and what must happen before the release is used" />
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "Recording…" : "Record review"}</button>
        </form>
      )}
    </section>
  );
}
