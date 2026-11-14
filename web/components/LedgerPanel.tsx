"use client";
import { useState } from "react";
import { apiConfigured } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
interface Entry { seq: number; ts: string; event: string; subject: Record<string, unknown>; hash: string }
interface LedgerResponse { verify: { ok: boolean; entries: number; head: string; problems: string[] }; recent: Entry[] }

const EVENT: Record<string, string> = {
  release_check: "Release check", question_check: "Question check", review: "Review", envelope_opened: "Envelope opened",
};

/** Chain of custody: every check and decision is a signed entry chained to the one before it. */
export function LedgerPanel({ entry }: { entry?: { seq?: number; hash?: string } }) {
  const [data, setData] = useState<LedgerResponse | null>(null);
  const [error, setError] = useState("");
  if (!apiConfigured) return null;
  async function check() {
    setError("");
    try {
      const res = await fetch(`${API}/ledger?limit=6`);
      if (!res.ok) throw new Error(`Couldn't read the ledger (${res.status}).`);
      setData(await res.json());
    } catch (e) { setError((e as Error).message); }
  }
  return (
    <section className="block ledger" aria-labelledby="ledger-h">
      <h3 id="ledger-h">Audit ledger</h3>
      <p className="quiet">
        Every check, envelope and review is a signed entry chained to the one before it, so no past result or
        decision can be edited, removed or reordered without it showing.
        {entry?.seq ? ` This result is entry #${entry.seq} (${entry.hash?.slice(0, 12)}).` : ""}
      </p>
      <div className="cert-actions"><button type="button" className="secondary" onClick={check}>Verify the ledger</button></div>
      {error && <p className="error" role="alert">{error}</p>}
      {data && (
        <>
          <p className="cert-result" data-state={data.verify.ok ? "valid" : "invalid"} role="status">
            {data.verify.ok
              ? `Chain intact: ${data.verify.entries} entries, head ${data.verify.head.slice(0, 16)}.`
              : `Chain broken: ${data.verify.problems[0]}`}
          </p>
          <div className="table-scroll"><table className="checks">
            <thead><tr><th scope="col">#</th><th scope="col">Event</th><th scope="col">Outcome</th><th scope="col">Hash</th></tr></thead>
            <tbody>{data.recent.map((e) => (
              <tr key={e.seq}><td>{e.seq}</td><td>{EVENT[e.event] ?? e.event}</td>
                <td>{String(e.subject.verdict ?? (typeof e.subject.decision === "string" ? e.subject.decision : e.subject.decision ? "per analysis" : e.subject.envelope ?? ""))}</td>
                <td><code>{e.hash.slice(0, 12)}</code></td></tr>
            ))}</tbody>
          </table></div>
        </>
      )}
    </section>
  );
}
