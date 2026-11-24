import Link from "next/link";
import { DEMO_MODE } from "@/lib/demo";

export function Nav({ current }: { current: "question" | "release" }) {
  return (
    <>
      {DEMO_MODE && (
        <p className="demo-banner" role="note">
          <strong>Public demo with synthetic data.</strong> Every ID here is made up and the values are random.
          Real TCGA-BRCA checks run locally from the{" "}
          <a href="https://github.com/NinadRao0707/cohort-firewall">GitHub repository</a>.
        </p>
      )}
      <nav className="tabs" aria-label="Checks">
        <Link href="/tower" aria-current={current === "release" ? "page" : undefined}>Release check</Link>
        <Link href="/" aria-current={current === "question" ? "page" : undefined}>Question check</Link>
      </nav>
    </>
  );
}
