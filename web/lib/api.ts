import type { EvaluateResponse } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export const apiConfigured = API.length > 0;

export interface EvaluateInput {
  dataset: File;
  dictionary?: File | null;
  spec?: string;       // QuestionSpec JSON
  question?: string;   // free text, parsed by the LLM on the server
}

export async function evaluate(input: EvaluateInput): Promise<EvaluateResponse> {
  const form = new FormData();
  form.append("dataset", input.dataset);
  if (input.dictionary) form.append("dictionary", input.dictionary);
  if (input.spec) form.append("spec", input.spec);
  if (input.question) {
    form.append("question", input.question);
    if (!input.spec) form.append("use_llm_parser", "true");
  }
  form.append("use_llm_report", "false");
  const res = await fetch(`${API}/evaluate`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`The firewall service returned ${res.status}. Check that the API is running.`);
  return res.json();
}

export async function verifyCertificate(certificate: unknown): Promise<boolean> {
  const res = await fetch(`${API}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ certificate }),
  });
  if (!res.ok) throw new Error(`Verification request failed with ${res.status}.`);
  return (await res.json()).valid === true;
}

export async function loadSample(name: string): Promise<EvaluateResponse> {
  const res = await fetch(`/samples/${name}.json`);
  if (!res.ok) throw new Error(`Sample "${name}" is missing from public/samples.`);
  return res.json();
}

export const SAMPLES: { name: string; label: string }[] = [
  { name: "tcga_q1_er_protein_vs_clinical", label: "TCGA: ER protein vs clinical ER" },
  { name: "tcga_q1b_er_protein_profiled_only", label: "TCGA: same, protein-profiled only" },
  { name: "tcga_q2_survival_5yr", label: "TCGA: 5-year overall survival" },
  { name: "tcga_q3_pfi_2yr_by_race", label: "TCGA: 2-year PFI across race" },
  { name: "tcga_q5_all_samples", label: "TCGA: all samples, not patients" },
  { name: "tcga_q6_patient_risk_score", label: "TCGA: patient risk score" },
  { name: "tcga_q7_pam50_subtype_mix", label: "TCGA: PAM50 subtype mix (two calls)" },
  { name: "clean", label: "2-year recurrence study" },
  { name: "q3_survival", label: "5-year survival model" },
  { name: "q2_clinical", label: "Treatment recommendation" },
  { name: "risk_score_question", label: "Patient risk score" },
  { name: "leakage", label: "Hidden outcome leak" },
  { name: "skewed_subgroup", label: "Underrepresented group" },
  { name: "phi", label: "Identifiers in the data" },
  { name: "prompt_injection", label: "Injection attempt" },
  { name: "no_dictionary", label: "No data dictionary" },
  { name: "synthea_small_q1_progression_2yr", label: "Synthea, small cohort: 2-year worsening" },
  { name: "synthea_large_q1_progression_2yr", label: "Synthea, large cohort: 2-year worsening" },
  { name: "synthea_large_q2_survival_5yr", label: "Synthea, large cohort: 5-year survival" },
];
