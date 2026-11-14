export type Verdict = "READY" | "CONDITIONAL" | "BLOCKED" | "INSUFFICIENT_EVIDENCE";

export interface Finding {
  rule_id: string;
  check: string;
  verdict: Verdict;
  reason: string;
  remedy: string;
  accepted?: boolean;
  accepted_as?: string;
  reconsider?: string;
  rule_condition?: string;
  measured?: Record<string, unknown>;
  finding_id?: string;
  check_performed?: string;
  fields_used?: string[];
  rows_or_groups_affected?: string;
  effect_on_intended_use?: string;
  materiality?: string;
  confidence?: string;
  evidence_or_source?: string;
  limitation?: string;
  uncertainty?: string;
  borderline?: boolean;
}

export interface QuestionStep { rank: number; rule_id: string; verdict: Verdict; action: string; size: string; unblocks: boolean; evidence_to_reconsider: string }

export interface CheckResult {
  check: string;
  status: "ok" | "not_evaluable" | "skipped";
  metrics: Record<string, unknown>;
  note: string;
}

export interface Certificate {
  cert_id: string;
  alg: string;
  signature: string;
  payload: {
    verdict: Verdict;
    dataset_sha256: string;
    dictionary_sha256: string | null;
    spec_sha256: string;
    policy_version: string;
    policy_sha256: string;
    engine_version: string;
    rule_ids: string[];
    issued_at: string;
  };
}

export interface EvaluateResponse {
  verdict: Verdict;
  human_review?: { level: "required" | "recommended"; text: string };
  notes?: string[];
  limitations?: string[];
  accepted_limitations?: { rule_id: string; as: string }[];
  ignored_acceptances?: string[];
  findings: Finding[];
  checks: CheckResult[];
  spec: { question_text?: string } & Record<string, unknown>;
  report: { text: string; source: "llm" | "template" };
  findings_template_csv?: string;
  x_ledger?: { seq?: number; hash?: string };
  shareable_summary?: { text: string; note: string };
  plain_summary?: string;
  next_steps?: QuestionStep[];
  funnel?: {
    steps: { step: string; n: number; dropped: number }[];
    n_final: number; n_patients_final: number | null; repeated_patients: number | null;
    not_in_data: string[]; note: string; samples_csv: string;
  };
  certificate: Certificate;
  engine_version: string;
  policy_version: string;
}

export const VERDICT_ORDER: Verdict[] = ["READY", "CONDITIONAL", "INSUFFICIENT_EVIDENCE", "BLOCKED"];

export const VERDICT_COPY: Record<Verdict, { label: string; line: string }> = {
  READY: { label: "Ready", line: "This dataset can support this question." },
  CONDITIONAL: { label: "Conditional", line: "Usable for this question after the changes listed below." },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient evidence",
    line: "The tool can't confirm something this question needs, so it doesn't pass by default.",
  },
  BLOCKED: { label: "Blocked", line: "This dataset can't be used for this question." },
};
