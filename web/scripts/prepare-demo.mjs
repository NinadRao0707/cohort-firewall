// Runs before `next build` on Vercel (see vercel.json). In demo mode it DELETES every saved sample
// that isn't on the synthetic allow-list, so files with real TCGA sample IDs can never be served,
// even by direct URL. It only touches the build's own copy; locally it does nothing unless
// NEXT_PUBLIC_DEMO_MODE=1 is set.
import { readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const demo = process.env.NEXT_PUBLIC_DEMO_MODE === "1" || !!process.env.VERCEL;
const ALLOW = new Set([
  "clean", "q3_survival", "q2_clinical", "risk_score_question", "leakage", "skewed_subgroup", "phi",
  "prompt_injection", "no_dictionary", "synthea_small_q1_progression_2yr", "synthea_small_q2_survival_5yr",
  "synthea_large_q1_progression_2yr", "synthea_large_q2_survival_5yr", "tower_demo",
]);
const dir = join(process.cwd(), "public", "samples");
if (!demo) {
  console.log("prepare-demo: not in demo mode, nothing removed");
} else {
  const removed = [];
  for (const f of readdirSync(dir)) {
    if (!ALLOW.has(f.replace(/\.json$/, ""))) { rmSync(join(dir, f)); removed.push(f); }
  }
  console.log(`prepare-demo: kept ${readdirSync(dir).length} synthetic samples, removed ${removed.length}: ${removed.join(", ")}`);
}
