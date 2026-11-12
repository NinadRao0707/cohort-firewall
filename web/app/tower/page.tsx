"use client";
import { useEffect, useRef, useState } from "react";
import { Nav } from "@/components/Nav";
import { TowerResults } from "@/components/TowerResults";
import { apiConfigured, buildRelease, listReleases, loadTowerSample, runTower, type FindingsDoc } from "@/lib/tower";

export default function TowerPage() {
  const [releases, setReleases] = useState<{ name: string; files: string[] }[]>([]);
  const [release, setRelease] = useState("");
  const [rna, setRna] = useState(true);
  const [doc, setDoc] = useState<FindingsDoc | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stage, setStage] = useState("");
  const out = useRef<HTMLElement>(null);

  async function refresh() {
    if (!apiConfigured) return;
    try {
      const r = await listReleases();
      setReleases(r);
      if (r.length && !release) setRelease(r[0].name);
    } catch (e) { setError((e as Error).message); }
  }
  useEffect(() => { refresh(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if ((doc || error) && window.matchMedia("(max-width: 860px)").matches)
      out.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [doc, error]);

  async function go(task: () => Promise<FindingsDoc>) {
    setBusy(true); setError("");
    try { setDoc(await task()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); setStage(""); }
  }

  async function buildAndCompare(file: File | undefined) {
    if (!file) return;
    go(async () => {
      let config: unknown;
      try { config = JSON.parse(await file.text()); } catch { throw new Error("That file is not valid JSON."); }
      setStage("Building the release with make_release.py…");
      const name = await buildRelease(config);
      await refresh();
      setRelease(name);
      setStage(`Comparing ${name} with the frozen release…`);
      const d = await runTower(name, rna);
      setStage("");
      return d;
    });
  }

  async function openFile(file: File | undefined) {
    if (!file) return;
    go(async () => {
      const d = JSON.parse(await file.text());
      if (d.format_version !== "0.2" || !Array.isArray(d.findings)) throw new Error("Not a findings.json in shared format v0.2.");
      return d;
    });
  }

  return (
    <main className="shell">
      <header className="masthead">
        <h1>Cohort Firewall</h1>
        <p>A new release arrived. See what changed and which analyses you can still trust.</p>
      </header>
      <Nav current="release" />
      <div className="layout">
        <aside className="panel">
          <form onSubmit={(e) => { e.preventDefault(); if (release) go(() => runTower(release, rna)); }}>
            <label className="field">
              <span>New release</span>
              <select value={release} onChange={(e) => setRelease(e.target.value)} disabled={!apiConfigured || !releases.length}>
                {releases.length === 0 && <option value="">{apiConfigured ? "No releases found" : "API not connected"}</option>}
                {releases.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
              </select>
              <small>Compared with the frozen release.</small>
            </label>
            <div className="submit-bar">
              <button type="submit" disabled={!apiConfigured || !release || busy}>{busy ? "Comparing…" : "Compare releases"}</button>
            </div>
          </form>
          <details className="group">
            <summary>Other ways to load a release</summary>
            <label className="field">
              <span>Build from a make_release config (JSON)</span>
              <input type="file" accept=".json,application/json" disabled={!apiConfigured || busy}
                     onChange={(e) => buildAndCompare(e.target.files?.[0])} />
              <small>Runs the event&apos;s make_release.py, then compares. Its answer key is never read.</small>
            </label>
            <label className="field">
              <span>Open a findings.json file</span>
              <input type="file" accept=".json,application/json" onChange={(e) => openFile(e.target.files?.[0])} />
            </label>
            <div className="actions">
              <button type="button" className="secondary" onClick={() => go(loadTowerSample)}>Open saved practice-B run</button>
              <button type="button" className="secondary" onClick={refresh} disabled={!apiConfigured || busy}>Refresh release list</button>
            </div>
            <label className="toggle"><input type="checkbox" checked={rna} onChange={(e) => setRna(e.target.checked)} /> Include the 64 MB RNA file</label>
          </details>
        </aside>
        <section className="output" aria-live="polite" ref={out}>
          {error && <p className="error" role="alert">{error}</p>}
          {busy && stage && <p className="quiet" role="status">{stage}</p>}
          {doc ? <TowerResults doc={doc} /> : (
            <div className="empty">
              <p>Pick a release and select Compare releases.</p>
              <p className="quiet">Analyses that nothing touches are left alone, and every change is listed for a person to decide.</p>
            </div>
          )}
        </section>
      </div>
      <footer className="disclaimer">Research data-quality tool. Not for diagnosis, treatment or patient risk scores.</footer>
    </main>
  );
}
