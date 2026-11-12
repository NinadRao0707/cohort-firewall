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
        <p>Cohort Control Tower: a new TCGA-BRCA release arrived. What changed, which analyses does it break, and which can you still trust?</p>
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
              <small>Folders in the challenge repo&apos;s data/tcga-brca/releases/. Compared with the frozen release.</small>
            </label>
            <label className="toggle"><input type="checkbox" checked={rna} onChange={(e) => setRna(e.target.checked)} /> Include the 64 MB RNA file</label>
            <div className="cert-actions">
              <button type="submit" disabled={!apiConfigured || !release || busy}>{busy ? "Comparing… (up to a minute)" : "Compare releases"}</button>
              <button type="button" className="secondary" onClick={refresh} disabled={!apiConfigured || busy}>Refresh list</button>
            </div>
          </form>
          <div className="samples">
            <h3>Or build a release from a config</h3>
            <label className="field">
              <span>make_release.py config (JSON)</span>
              <input type="file" accept=".json,application/json" disabled={!apiConfigured || busy}
                     onChange={(e) => buildAndCompare(e.target.files?.[0])} />
              <small>Runs the event&apos;s own make_release.py --config, then compares. Its answer key is never read.</small>
            </label>
          </div>
          <div className="samples">
            <h3>Or open results</h3>
            <label className="field">
              <span>A findings.json file</span>
              <input type="file" accept=".json,application/json" onChange={(e) => openFile(e.target.files?.[0])} />
            </label>
            <button type="button" className="link" onClick={() => go(loadTowerSample)}>Saved run: practice-B</button>
          </div>
        </aside>
        <section className="output" aria-live="polite" ref={out}>
          {error && <p className="error" role="alert">{error}</p>}
          {busy && stage && <p className="quiet" role="status">{stage}</p>}
          {doc ? <TowerResults doc={doc} /> : (
            <div className="empty">
              <p>Pick a new release and compare it with the frozen baseline, or open a saved result.</p>
              <p className="quiet">Unaffected analyses are not rerun. Every change and every repair is listed for a person to decide.</p>
            </div>
          )}
        </section>
      </div>
      <footer className="disclaimer">
        Research data-quality check. Not a clinical tool: no diagnosis, treatment recommendation, or patient
        risk score, and no claim of clinical validity or regulatory compliance.
      </footer>
    </main>
  );
}
