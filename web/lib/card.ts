import type { EvaluateResponse } from "./types";
import type { FindingsDoc } from "./tower";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ColumnInfo {
  name: string; type?: string; role?: string; timing?: string; unit?: string | null;
  description: string; missing: number; min?: number | null; max?: number | null;
  values?: { value: string | number; n: number }[];
}
export interface DatasetInfo { id: string; label: string; n_rows: number; columns: ColumnInfo[] }
export interface Acceptable { rule_id: string; label: string }

export interface Spec {
  question_text: string;
  task_type: "binary_classification" | "survival" | "descriptive" | "regression";
  intended_use: "research" | "model_development" | "clinical_decision_support" | "direct_patient_care";
  cancer_type?: string | null;
  population_filters: { column: string; op: string; value: unknown }[];
  outcome_column?: string | null;
  outcome_positive_value?: unknown;
  time_column?: string | null;
  time_horizon_months?: number | null;
  feature_columns: string[];
  subgroup_columns: string[];
  acceptable_limitations: string[];
  parse_confidence?: number;
}

export interface ReviewRecord {
  review: {
    review_id: string; type: "question" | "release"; created_at: string; note: string;
    reviewer: { name: string; role: string };
    decision?: string; decisions?: { analysis: string; verdict: string; decision: string }[];
    acknowledged_findings: string[];
    subject: Record<string, unknown>;
  };
  signature: string; alg: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Request failed (${res.status}).`);
  return res.json();
}
const post = (path: string, body: unknown) =>
  fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const listDatasets = async () => (await json<{ datasets: { id: string; label: string }[] }>(await fetch(`${API}/datasets`))).datasets;
export const describeDataset = async (id: string) => json<DatasetInfo>(await fetch(`${API}/datasets/${id}`));
export const getAcceptable = async () => (await json<{ acceptable: Acceptable[] }>(await fetch(`${API}/policy/acceptable`))).acceptable;
export const exampleCards = async (id: string) =>
  (await json<{ cards: { id: string; spec: Spec }[] }>(await fetch(`${API}/examples/cards/${id}`))).cards;
export const evaluateCard = async (dataset_id: string, spec: Spec) => json<EvaluateResponse>(await post("/evaluate-card", { dataset_id, spec }));

export const reviewQuestion = async (body: { result: EvaluateResponse; reviewer: string; role: string; decision: string; acknowledged: string[]; note: string }) =>
  json<ReviewRecord>(await post("/review/question", body));
export const reviewRelease = async (body: { findings: FindingsDoc; reviewer: string; role: string; decisions: Record<string, string>; acknowledged: string[]; note: string }) =>
  json<ReviewRecord>(await post("/review/release", body));

export const DECISION_LABEL: Record<string, string> = {
  approve: "Approve use for this question",
  approve_with_conditions: "Approve with conditions",
  reject: "Reject: do not use",
  request_more: "Ask for more evidence",
};
export const DECISIONS_FOR: Record<string, string[]> = {
  READY: ["approve", "reject", "request_more"], Ready: ["approve", "reject", "request_more"],
  CONDITIONAL: ["approve_with_conditions", "reject", "request_more"], Conditional: ["approve_with_conditions", "reject", "request_more"],
  BLOCKED: ["reject", "request_more"], Blocked: ["reject", "request_more"],
  INSUFFICIENT_EVIDENCE: ["reject", "request_more"], "Insufficient Evidence": ["reject", "request_more"],
};

export function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
