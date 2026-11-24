import type { ReactNode } from "react";
/** Shown in place of a feature that needs the local API (the hosted demo has none). */
export function LocalOnly({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="block local-only" aria-label={title}>
      <h3>{title}</h3>
      <p className="quiet">{children}</p>
      <p className="quiet">
        To try it, run the tool locally: clone the{" "}
        <a href="https://github.com/NinadRao0707/cohort-firewall">GitHub repository</a>, then{" "}
        <code>bash scripts/setup.sh</code> and <code>bash scripts/run.sh</code>.
      </p>
    </section>
  );
}
