import type { EvaluateResponse } from "@/lib/types";
import { CertificatePanel } from "./CertificatePanel";
import { ChecksTable } from "./ChecksTable";
import { Findings } from "./Findings";
import { Funnel } from "./Funnel";
import { QuestionReview } from "./ReviewPanel";
import { NextSteps } from "./Summary";
import { Tabs } from "./Tabs";
import { VerdictGate } from "./VerdictGate";

export function Results({ result }: { result: EvaluateResponse }) {
  const counted = result.findings.filter((f) => !f.accepted).length;
  return (
    <div className="results">
      <VerdictGate verdict={result.verdict}
                   cant={["whether the research answer will be meaningful: it checks the data, not the science",
                          "about problems its rules don't cover, so Ready is not proof the data is flawless"]}
                   summary={result.plain_summary?.replace(/^[^.]*\.\s*/, "")} review={result.human_review} />
      <Tabs initial={counted ? "steps" : "samples"} tabs={[
        { id: "steps", label: "Next steps", count: result.next_steps?.length ?? 0,
          content: <NextSteps steps={result.next_steps} /> },
        { id: "findings", label: "Findings", count: result.findings.length,
          content: <Findings findings={result.findings} csv={result.findings_template_csv} name={result.certificate?.cert_id} /> },
        { id: "samples", label: "Samples",
          content: <Funnel funnel={result.funnel} name={result.certificate?.cert_id} /> },
        { id: "checks", label: "All checks", content: (
          <>
            <ChecksTable checks={result.checks} findings={result.findings} />
            {(result.notes?.length ?? 0) > 0 && (
              <details className="fold"><summary>Data notes ({result.notes!.length})</summary>
                <ul className="plain-list">{result.notes!.map((n) => <li key={n}>{n}</li>)}</ul></details>
            )}
            <details className="fold"><summary>Limitations of this check</summary>
              <ul className="plain-list">{(result.limitations ?? []).map((l) => <li key={l}>{l}</li>)}</ul></details>
          </>
        ) },
        { id: "review", label: "Review", content: (
          <>
            <QuestionReview key={result.certificate.cert_id} result={result} />
            <CertificatePanel cert={result.certificate} />
          </>
        ) },
      ]} />
    </div>
  );
}
