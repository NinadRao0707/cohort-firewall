import type { EvaluateResponse } from "@/lib/types";
import { CertificatePanel } from "./CertificatePanel";
import { ChecksTable } from "./ChecksTable";
import { Findings } from "./Findings";
import { HumanReview, NotesAndLimits } from "./ReviewAndLimits";
import { QuestionReview } from "./ReviewPanel";
import { Summary } from "./Summary";
import { Funnel } from "./Funnel";
import { VerdictGate } from "./VerdictGate";

export function Results({ result }: { result: EvaluateResponse }) {
  return (
    <div className="results">
      <div>
        <VerdictGate verdict={result.verdict} question={result.spec?.question_text as string | undefined} />
        <HumanReview review={result.human_review} />
      </div>
      <Summary text={result.plain_summary} steps={result.next_steps} />
      <Funnel funnel={result.funnel} name={result.certificate?.cert_id} />
      <Findings findings={result.findings} csv={result.findings_template_csv} name={result.certificate?.cert_id} />
      <ChecksTable checks={result.checks} findings={result.findings} />
      <NotesAndLimits notes={result.notes} limitations={result.limitations} />
      <QuestionReview key={result.certificate.cert_id} result={result} />
      <CertificatePanel cert={result.certificate} />
    </div>
  );
}
