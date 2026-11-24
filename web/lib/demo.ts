/** Hosted (public) demo mode: synthetic examples only. Set NEXT_PUBLIC_DEMO_MODE=1, or deploy on
 *  Vercel, where next.config.mjs turns it on automatically. Real TCGA runs stay local. */
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

/** Saved results made only from synthetic data with made-up IDs. Must match scripts/prepare-demo.mjs. */
export const SYNTHETIC_SAMPLES = new Set([
  "clean", "q3_survival", "q2_clinical", "risk_score_question", "leakage", "skewed_subgroup", "phi",
  "prompt_injection", "no_dictionary", "synthea_small_q1_progression_2yr", "synthea_small_q2_survival_5yr",
  "synthea_large_q1_progression_2yr", "synthea_large_q2_survival_5yr", "tower_demo",
]);
