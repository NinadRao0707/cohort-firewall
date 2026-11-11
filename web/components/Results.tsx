import type { EvaluateResponse } from "@/lib/types";
import { CertificatePanel } from "./CertificatePanel";
import { ChecksTable } from "./ChecksTable";
import { Findings } from "./Findings";
import { HumanReview, NotesAndLimits } from "./ReviewAndLimits";
import { VerdictGate } from "./VerdictGate";

export function Results({ result }: { result: EvaluateResponse }) {
  return (
    <div className="results">
      <div>
        <VerdictGate verdict={result.verdict} question={result.spec?.question_text as string | undefined} />
        <HumanReview review={result.human_review} />
      </div>
      <Findings findings={result.findings} />
      <ChecksTable checks={result.checks} findings={result.findings} />
      <NotesAndLimits notes={result.notes} limitations={result.limitations} />
      <CertificatePanel cert={result.certificate} />
    </div>
  );
}
