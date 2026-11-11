export type Verdict = "READY" | "CONDITIONAL" | "BLOCKED" | "INSUFFICIENT_EVIDENCE";

export interface Finding {
  rule_id: string;
  check: string;
  verdict: Verdict;
  reason: string;
  remedy: string;
}

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
  findings: Finding[];
  checks: CheckResult[];
  spec: { question_text?: string } & Record<string, unknown>;
  report: { text: string; source: "llm" | "template" };
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
    line: "The dataset isn't documented well enough to decide. Nothing passes by default.",
  },
  BLOCKED: { label: "Blocked", line: "This dataset can't be used for this question." },
};
