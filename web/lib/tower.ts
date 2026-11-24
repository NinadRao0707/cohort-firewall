import { DEMO_MODE } from "./demo";
import { apiConfigured } from "./api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export type ShareVerdict = "Ready" | "Conditional" | "Blocked" | "Insufficient Evidence";

export interface EvidenceRef { kind: string; id: string; release?: string; file?: string; note?: string }

export interface TowerFinding {
  id: string; kind?: string; summary: string;
  severity: "high" | "medium" | "low" | "none"; confidence: "high" | "medium" | "low";
  evidence: EvidenceRef[]; affects_analyses?: string[]; not_affected_analyses?: string[];
  limitation?: string; needs_human_review?: boolean;
  x_severity_reason?: string; x_summary_of_other_findings?: boolean; x_p_by_chance?: number;
  x_confidence_reason?: string;
}

export interface TowerAnalysis {
  id: string; status: "unchanged" | "changed" | "not_rerun"; description?: string; inputs?: string[];
  reason?: string; verdict?: ShareVerdict;
  verdict_rules?: { rule_id: string; verdict: ShareVerdict; reason: string; remedy: string }[];
  affected_by?: string[]; needs_human_review?: boolean;
  before?: Record<string, unknown>; after?: Record<string, unknown>;
  x_impact?: {
    noise?: { kind: string; metric: string; ratio: number; label: string; noise: number; noise_name: string;
              delta?: number; before?: number; after?: number; shift?: number; baseline_ci95?: number[];
              after_inside_baseline_ci?: boolean } | null;
    repair?: { metric: string; baseline: number; new_release: number; after_all_repairs: number; back_to_baseline: boolean;
               by_kind: { kind: string; findings: string[]; share_of_shift_pct: number }[] } | null;
    sentence?: string;
  };
}

export interface TowerRepair {
  id: string; action: string; targets: EvidenceRef[]; justification: string; addresses: string[];
}

export interface FindingsDoc {
  format_version: string;
  producer: { team: string; product: string; track: string };
  data: { dataset?: string; releases: { name: string; files: { file: string; sha256: string; hash_of?: string }[] }[] };
  question: string; verdict?: ShareVerdict;
  findings: TowerFinding[]; analyses?: TowerAnalysis[]; repairs?: TowerRepair[];
  limitations?: string[]; certificate?: unknown; baseline_unverified_files?: string[];
  timing_seconds?: { baseline: number; total: number };
  not_compared?: string[];
  x_ledger?: { seq?: number; hash?: string };
  x_shareable_summary?: { text: string; note: string };
  x_site_check?: { changed_samples: number; sites: number; top_site: string; in_top_site: number;
                   expected_in_top_site: number | null; p_by_chance: number | null } | null;
  plain_summary?: string;
  next_steps?: { rank: number; action: string; samples: string[]; n_samples: number; resolves: string[];
                 affects_analyses: string[]; evidence_to_reconsider?: string }[];
  x_summaries?: TowerFinding[];
  x_headline?: string;
}

export async function listReleases(): Promise<{ name: string; files: string[] }[]> {
  const res = await fetch(`${API}/tower/releases`);
  if (!res.ok) throw new Error(`Could not list releases (${res.status}).`);
  return (await res.json()).releases;
}

export async function runTower(release: string, includeRna: boolean): Promise<FindingsDoc> {
  const res = await fetch(`${API}/tower/run`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ release, include_rna: includeRna }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Run failed (${res.status}).`);
  return res.json();
}

export async function unsealEnvelope(envelope: string, code: string): Promise<string> {
  const res = await fetch(`${API}/tower/unseal`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ envelope, code }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Couldn't open the envelope (${res.status}).`);
  return (await res.json()).name;
}

export async function buildRelease(config: unknown): Promise<string> {
  const res = await fetch(`${API}/tower/build`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ config }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Build failed (${res.status}).`);
  return (await res.json()).name;
}

export async function loadTowerSample(): Promise<FindingsDoc> {
  const res = await fetch(DEMO_MODE ? "/samples/tower_demo.json" : "/samples/tower_practice-B.json");
  if (!res.ok) throw new Error("No saved Control Tower sample. Run scripts/export_web_samples.py.");
  return res.json();
}

export { apiConfigured };
