import type { EvaluateResponse } from "@/lib/types";
import { CertificatePanel } from "./CertificatePanel";
import { ChecksTable } from "./ChecksTable";
import { Findings } from "./Findings";
import { VerdictGate } from "./VerdictGate";

export function Results({ result }: { result: EvaluateResponse }) {
  return (
    <div className="results">
      <VerdictGate verdict={result.verdict} question={result.spec?.question_text as string | undefined} />
      <Findings findings={result.findings} />
      <ChecksTable checks={result.checks} findings={result.findings} />
      <CertificatePanel cert={result.certificate} />
    </div>
  );
}
