"use client";
import { useState } from "react";
import { apiConfigured, verifyCertificate } from "@/lib/api";
import type { Certificate } from "@/lib/types";

const short = (h: string | null) => (h ? `${h.slice(0, 12)}…${h.slice(-6)}` : "none");

export function CertificatePanel({ cert }: { cert: Certificate }) {
  const [state, setState] = useState<"idle" | "checking" | "valid" | "invalid" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onVerify() {
    setState("checking");
    try {
      setState((await verifyCertificate(cert)) ? "valid" : "invalid");
    } catch (e) {
      setState("error");
      setMessage((e as Error).message);
    }
  }

  function onDownload() {
    const blob = new Blob([JSON.stringify(cert, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cohort-firewall-certificate-${cert.cert_id}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const p = cert.payload;
  return (
    <section className="block">
      <h3>Readiness certificate</h3>
      <p className="quiet">
        Signed record of this decision. Changing the data, question, or rules produces a different certificate.
      </p>
      <dl className="cert">
        <dt>Certificate</dt><dd className="hash">{cert.cert_id}</dd>
        <dt>Dataset</dt><dd className="hash">{short(p.dataset_sha256)}</dd>
        <dt>Dictionary</dt><dd className="hash">{short(p.dictionary_sha256)}</dd>
        <dt>Question</dt><dd className="hash">{short(p.spec_sha256)}</dd>
        <dt>Policy</dt><dd>v{p.policy_version}</dd>
        <dt>Issued</dt><dd>{new Date(p.issued_at).toLocaleString()}</dd>
      </dl>
      <div className="cert-actions">
        <button type="button" onClick={onVerify} disabled={!apiConfigured || state === "checking"}>
          {state === "checking" ? "Verifying…" : "Verify signature"}
        </button>
        <button type="button" className="secondary" onClick={onDownload}>Download certificate</button>
      </div>
      <p className="cert-result" role="status" data-state={state}>
        {state === "valid" && "Signature valid. This record has not been changed."}
        {state === "invalid" && "Signature does not match. This record was changed after it was issued."}
        {state === "error" && message}
        {state === "idle" && !apiConfigured && "Start the API to verify signatures."}
      </p>
    </section>
  );
}
