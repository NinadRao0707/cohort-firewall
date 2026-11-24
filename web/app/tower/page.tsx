"use client";
import { useEffect, useRef, useState } from "react";
import { Nav } from "@/components/Nav";
import { DEMO_MODE } from "@/lib/demo";
import { ChipPopover } from "@/components/Popover";
import { TowerResults } from "@/components/TowerResults";
import { apiConfigured, buildRelease, listReleases, loadTowerSample, runTower, unsealEnvelope, type FindingsDoc } from "@/lib/tower";

export default function TowerPage() {
  const [releases, setReleases] = useState<{ name: string; files: string[] }[]>([]);
  const [release, setRelease] = useState("");
  const [rna, setRna] = useState(true);
  const [doc, setDoc] = useState<FindingsDoc | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [envNo, setEnvNo] = useState("");
  const [envCode, setEnvCode] = useState("");
  const out = useRef<HTMLElement>(null);

  async function refresh(select?: string) {
    if (!apiConfigured) return;
    try {
      const r = await listReleases();
      setReleases(r);
      if (select) setRelease(select);
      else if (r.length && !release) setRelease(r[0].name);
    } catch (e) { setError((e as Error).message); }
  }
  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (doc || error) out.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [doc, error]);

  async function go(task: () => Promise<FindingsDoc>) {
    setBusy(true); setError(""); setDoc(null);
    try { setDoc(await task()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); setStage(""); }
  }
  function openEnvelope() {
    go(async () => {
      setStage(`Opening envelope ${envNo}… (about 15 s)`);
      const name = await unsealEnvelope(envNo, envCode);
      await refresh(name);
      setStage(`Comparing ${name}…`);
      return runTower(name, rna);
    });
  }

  function buildAndCompare(file: File | undefined) {
    if (!file) return;
    go(async () => {
      let config: unknown;
      try { config = JSON.parse(await file.text()); } catch { throw new Error("That file isn't valid JSON."); }
      setStage("Building the release…");
      const name = await buildRelease(config);
      await refresh(name);
      setStage(`Comparing ${name}…`);
      return runTower(name, rna);
    });
  }
  function openFile(file: File | undefined) {
    if (!file) return;
    go(async () => {
      const d = JSON.parse(await file.text());
      if (d.format_version !== "0.2" || !Array.isArray(d.findings)) throw new Error("That isn't a findings.json in shared format v0.2.");
      return d;
    });
  }

  return (
    <main className="shell">
      <header className="masthead">
        <h1>Cohort Firewall</h1>
        <p>A new release arrived. What changed, and what can you still trust?</p>
      </header>
      <Nav current="release" />
      <section className="toolbar" aria-label="Release">
        <form className="qbar" onSubmit={(e) => { e.preventDefault(); if (release) { setStage(`Comparing ${release}…`); go(() => runTower(release, rna)); } }}>
          <div className="chips-row">
            <ChipPopover variant="add" title="Open a sealed envelope" label="+ Open envelope" width={340}>
              {(close) => (
                <div className="editor">
                  <p className="quiet pop-note">Type the envelope number and the four-word code the judge gives you.
                    This runs the event&apos;s envelopes/unseal.py, then compares the release inside.</p>
                  <label className="field"><span>Envelope</span>
                    <input value={envNo} onChange={(e) => setEnvNo(e.target.value)} placeholder="07, or practice" inputMode="text" /></label>
                  <label className="field"><span>Code</span>
                    <input value={envCode} onChange={(e) => setEnvCode(e.target.value)} placeholder="amber falcon river quartz" autoCapitalize="none" /></label>
                  <button type="button" disabled={!apiConfigured || busy || !envNo.trim() || envCode.trim().split(/[\s-]+/).length !== 4}
                          onClick={() => { close(); openEnvelope(); }}>Open and compare</button>
                </div>
              )}
            </ChipPopover>
            <ChipPopover title="New release" label={<><span className="k">Release</span> {release || (apiConfigured ? "none found" : "saved results only")}</>}>
              {(close) => (
                <ul className="menu">{releases.map((r) => (
                  <li key={r.name}><label className="radio-row"><input type="radio" checked={r.name === release}
                    onChange={() => { setRelease(r.name); close(); }} /> {r.name}</label></li>
                ))}{releases.length === 0 && <li className="quiet">No release folders found.</li>}</ul>
              )}
            </ChipPopover>
            <span className="chip-static"><span className="k">Compared with</span> the frozen release</span>
            <ChipPopover variant="plain" title="More options" label="More" width={360}>
              {() => (
                <div className="editor">
                  <label className="field"><span>Build a release from a make_release config</span>
                    <input type="file" accept=".json,application/json" disabled={!apiConfigured || busy}
                           onChange={(e) => buildAndCompare(e.target.files?.[0])} />
                    <small>Runs the event&apos;s make_release.py, then compares. Its answer key is never read.</small></label>
                  <label className="field"><span>Open a findings.json file</span>
                    <input type="file" accept=".json,application/json" onChange={(e) => openFile(e.target.files?.[0])} /></label>
                  <button type="button" className="secondary" onClick={() => go(loadTowerSample)}>{DEMO_MODE ? "Open the synthetic demo run" : "Open the saved practice-B run"}</button>
                  <button type="button" className="secondary" onClick={() => refresh()} disabled={!apiConfigured || busy}>Refresh the release list</button>
                  <label className="radio-row"><input type="checkbox" checked={rna} onChange={(e) => setRna(e.target.checked)} /> Include the 64 MB RNA file</label>
                </div>
              )}
            </ChipPopover>
            <button type="submit" className="run" disabled={!apiConfigured || !release || busy}>{busy ? "Comparing…" : "Compare releases"}</button>
          </div>
          {busy && stage && <p className="quiet" role="status">{stage}</p>}
        </form>
      </section>
      <section className="output" aria-live="polite" ref={out}>
        {error && <p className="error" role="alert">{error}</p>}
        {doc ? <TowerResults doc={doc} /> : (
          <div className="empty">
            <p>{apiConfigured ? "Choose a release and select Compare releases." : (DEMO_MODE ? "This public demo uses synthetic data: open More, then the synthetic demo run." : "This copy shows saved results only: open More, then the saved practice-B run.")}</p>
            <p className="quiet">Analyses that nothing touches are left alone, and every change is listed for a person to decide.</p>
          </div>
        )}
      </section>
      <footer className="disclaimer">Research data-quality tool. Not for diagnosis, treatment or patient risk scores.</footer>
    </main>
  );
}
