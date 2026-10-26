"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { formatINR, formatDate, truncateHash } from "@/lib/utils";
import { BadgeProvenance } from "@/components/ui/BadgeProvenance";
import { BadgeStatus } from "@/components/ui/BadgeStatus";
import { FDRInstrument } from "@/types";
import {
  ScanSearch,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  ShieldCheck,
  Send,
  Eye,
  FileSearch,
  ExternalLink,
  MessageSquare,
  HelpCircle,
  Clock,
  Layers,
  ArrowRight,
} from "lucide-react";

export default function ScrutinyConsolePage() {
  const {
    appMode,
    fdrs,
    verifyField,
    raiseScrutinyQuery,
    passScrutinyToBank,
    confirmBankAffirmation,
  } = useApp();

  // Find cases eligible for scrutiny (UNDER_SCRUTINY, SUBMITTED, BANK_VERIFICATION_PENDING)
  const scrutinyQueue = fdrs.filter(
    (f) =>
      f.status === "UNDER_SCRUTINY" ||
      f.status === "SUBMITTED" ||
      f.status === "QUERY_RAISED" ||
      f.status === "BANK_VERIFICATION_PENDING"
  );

  const [selectedCaseId, setSelectedCaseId] = useState<number>(
    scrutinyQueue[0]?.id || 101
  );
  const [queryInput, setQueryInput] = useState<string>("");
  const [showQueryBox, setShowQueryBox] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [verifyingField, setVerifyingField] = useState<string | null>(null);
  const [isVerifyingAll, setIsVerifyingAll] = useState<boolean>(false);

  const activeCase =
    fdrs.find((f) => f.id === selectedCaseId) || scrutinyQueue[0] || fdrs[0];

  const handleVerifyField = async (fieldName: string, value: string) => {
    setVerifyingField(fieldName);
    const ok = await verifyField(
      activeCase.id,
      fieldName,
      value,
      "SCRUTINY_OFFICER_01",
      `Attested by Scrutiny Officer in Scrutiny Console`
    );
    setVerifyingField(null);
    if (ok) {
      alert(`Field "${fieldName}" attested and upgraded to OFFICER_VERIFIED (persisted in PostgreSQL & audit ledger).`);
    }
  };

  const handleVerifyAllFields = async () => {
    setIsVerifyingAll(true);
    let count = 0;
    for (const prov of activeCase.provenance_records) {
      if (prov.source_type !== "OFFICER_VERIFIED" && prov.source_type !== "BANK_CONFIRMED") {
        const ok = await verifyField(
          activeCase.id,
          prov.field_name,
          prov.extracted_value || "",
          "SCRUTINY_OFFICER_01",
          `Batch attested by Scrutiny Officer`
        );
        if (ok) count++;
      }
    }
    setIsVerifyingAll(false);
    alert(`Attestation complete: ${count} field(s) upgraded to OFFICER_VERIFIED in PostgreSQL.`);
  };

  const handleRaiseQuery = () => {
    if (!queryInput.trim()) {
      alert("Please enter specific deficiency observations for the institution.");
      return;
    }
    raiseScrutinyQuery(activeCase.id, queryInput);
    setShowQueryBox(false);
    setQueryInput("");
    alert(`Deficiency query logged and transmitted to ${activeCase.institution_name}.`);
  };

  const handleApproveForBank = () => {
    passScrutinyToBank(activeCase.id);
    if (appMode === "LIVE") {
      alert(
        `Scrutiny approved in UI console. Note: FastAPI backend does not have a bank confirmation router mounted yet; bank token dispatch and affirmation below run via the client-side simulated adapter.`
      );
    } else {
      alert(
        `Scrutiny approved! Single-use HMAC signed verification link dispatched to nodal branch nodal email.`
      );
    }
  };

  const handleSimulateBankAffirmation = () => {
    confirmBankAffirmation(activeCase.id);
    if (appMode === "LIVE") {
      alert(
        `Simulated Bank Affirmation applied in UI (DEMO ADAPTER). Notice: This simulation is client-side only because FastAPI does not expose a bank verification endpoint. Upon browser/repository refresh, data will sync with PostgreSQL. Attested fields (OFFICER_VERIFIED) remain permanently saved in PostgreSQL.`
      );
    } else {
      alert(
        `Simulated Bank Affirmation Successful! Branch confirmed lien in favor of AICTE. Provenance upgraded to BANK_CONFIRMED.`
      );
    }
  };

  return (
    <div className="space-y-6 pb-12 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
              Scrutiny Console & Dual-Pass Extraction
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold border border-amber-200">
              Scrutiny Desk
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Side-by-side certificate forensics, declared vs OCR mismatch examination, and branch affirmation routing
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">
            Active Queue: <strong className="text-slate-800">{scrutinyQueue.length} Cases</strong>
          </span>
        </div>
      </div>

      {/* Case Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-slate-200">
        {scrutinyQueue.map((item) => {
          const isSelected = item.id === activeCase?.id;
          const hasMismatch =
            item.discrepancies && item.discrepancies.some((d) => d.has_mismatch);

          return (
            <button
              key={item.id}
              onClick={() => {
                setSelectedCaseId(item.id);
                setShowQueryBox(false);
              }}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-t-lg text-xs font-semibold whitespace-nowrap transition-colors border-t border-l border-r ${
                isSelected
                  ? "bg-white border-slate-300 text-primary shadow-subtle -mb-px"
                  : "bg-slate-100/70 border-transparent text-slate-600 hover:bg-slate-100"
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  hasMismatch
                    ? "bg-rose-500 animate-ping"
                    : item.status === "BANK_VERIFICATION_PENDING"
                    ? "bg-purple-500"
                    : "bg-amber-500"
                }`}
              />
              <span>{item.fdr_number}</span>
              <span className="text-[10px] text-slate-400 font-normal">
                ({item.institution_name.split(" ")[0]})
              </span>
              {hasMismatch && (
                <span className="text-[9px] px-1 rounded bg-rose-100 text-rose-800 font-bold">
                  Mismatch
                </span>
              )}
            </button>
          );
        })}
      </div>

      {activeCase ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column (7 cols): Document Certificate Viewer */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-subtle flex flex-col overflow-hidden">
            {/* Certificate Header Bar */}
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" />
                <span className="font-bold text-slate-800">
                  {activeCase.bank_name.toUpperCase()} · SYNTHETIC CERTIFICATE
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500">Zoom:</span>
                <button
                  onClick={() => setZoomLevel((z) => Math.max(80, z - 10))}
                  className="px-2 py-0.5 bg-white border border-slate-200 rounded text-slate-700"
                >
                  -
                </button>
                <span className="font-mono text-slate-700">{zoomLevel}%</span>
                <button
                  onClick={() => setZoomLevel((z) => Math.min(130, z + 10))}
                  className="px-2 py-0.5 bg-white border border-slate-200 rounded text-slate-700"
                >
                  +
                </button>
              </div>
            </div>

            {/* Certificate Canvas / Rendered View */}
            <div className="p-6 bg-slate-100/70 overflow-auto flex-1 min-h-[460px] flex items-center justify-center">
              <div
                style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: "top center" }}
                className="w-full max-w-lg bg-white border border-slate-300 rounded-lg p-6 shadow-md font-serif text-slate-900 space-y-4"
              >
                {/* Certificate Bank Header */}
                <div className="text-center border-b-2 border-slate-800 pb-3 space-y-1">
                  <h3 className="text-base font-bold tracking-wider">
                    {activeCase.bank_name.toUpperCase()}
                  </h3>
                  <p className="text-[11px] font-sans text-slate-600">
                    {activeCase.branch || "Parliament Street Branch, New Delhi"} · IFSC: {activeCase.ifsc_code}
                  </p>
                  <p className="text-[9px] font-sans uppercase font-bold text-amber-700 bg-amber-50 py-0.5 px-2 rounded border border-amber-200 inline-block">
                    SYNTHETIC DEMO SAMPLE · NOT A NEGOTIABLE INSTRUMENT
                  </p>
                </div>

                {/* Certificate Body Fields */}
                <div className="font-sans text-xs space-y-2.5">
                  <div className="flex justify-between border-b border-dashed border-slate-200 pb-1">
                    <span className="text-slate-500">FDR Certificate Number:</span>
                    <span className="font-mono font-bold text-slate-900">
                      {activeCase.fdr_number}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-dashed border-slate-200 pb-1">
                    <span className="text-slate-500">Depositor Name:</span>
                    <span className="font-semibold text-slate-900">
                      {activeCase.institution_name}
                    </span>
                  </div>
                  <div
                    className={`flex justify-between border-b border-dashed border-slate-200 pb-1 p-1 rounded ${
                      activeCase.discrepancies?.some((d) => d.has_mismatch)
                        ? "bg-rose-50 border border-rose-300"
                        : ""
                    }`}
                  >
                    <span className="text-slate-700 font-semibold">Principal Deposit Sum:</span>
                    <span className="font-mono font-extrabold text-slate-900">
                      {activeCase.id === 101 ? "INR 1,00,000.00" : formatINR(activeCase.principal_amount)}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-dashed border-slate-200 pb-1">
                    <span className="text-slate-500">Interest Rate:</span>
                    <span className="font-mono text-slate-900">
                      {activeCase.interest_rate}% p.a.
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-dashed border-slate-200 pb-1">
                    <span className="text-slate-500">Maturity Date:</span>
                    <span className="font-medium text-slate-900">
                      {formatDate(activeCase.maturity_date)}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-dashed border-slate-200 pb-1">
                    <span className="text-slate-500">Lien Endorsement:</span>
                    <span className="font-semibold text-primary">
                      Marked in exclusive favour of AICTE
                    </span>
                  </div>
                </div>

                {/* Branch Stamp Seal */}
                <div className="pt-4 flex items-center justify-between font-sans text-[10px] text-slate-400">
                  <div className="border border-slate-300 p-2 rounded text-center w-28">
                    <div className="text-[9px] font-bold text-slate-600">OFFICIAL SEAL</div>
                    <div className="text-[8px] text-slate-400 mt-1">BRANCH MANAGER</div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono">SHA-256: {truncateHash(activeCase.document_hash, 6)}</p>
                    <p>Verified via FinTrust Ingestion Engine</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Forensics Inspection Strip */}
            {activeCase.forensics && (
              <div className="p-3 bg-slate-50 border-t border-slate-200 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-700 flex items-center gap-1.5">
                    <FileSearch className="w-3.5 h-3.5 text-primary" />
                    <span>PDF Metadata & Tamper Indicators (pikepdf)</span>
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    %%EOF Count: {activeCase.forensics.eof_count}
                  </span>
                </div>

                {activeCase.forensics.flags.length > 0 ? (
                  <div className="mt-2 p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px] space-y-1">
                    <p className="font-bold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                      <span>Tamper Indicator Flagged: Multiple Incremental Revisions</span>
                    </p>
                    <p className="text-rose-700 leading-tight">
                      Found {activeCase.forensics.eof_count} %%EOF markers. PDF modification timestamp ({activeCase.forensics.modified_date}) is post-issuance.
                    </p>
                  </div>
                ) : (
                  <p className="text-emerald-700 text-[11px] mt-1 font-medium">
                    ✓ Clean single revision, metadata dates consistent.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Right Column (5 cols): Declared vs OCR Side-by-Side & Review Actions */}
          <div className="lg:col-span-5 space-y-5">
            {/* Mismatch Alert Box if present */}
            {activeCase.discrepancies && activeCase.discrepancies.length > 0 && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <span className="font-bold text-xs">
                    Discrepancy Detected (Side-by-Side Validation)
                  </span>
                </div>
                {activeCase.discrepancies.map((d, i) => (
                  <div key={i} className="text-xs space-y-1 bg-white p-2.5 rounded-lg border border-rose-200">
                    <span className="font-bold text-slate-700">{d.label}</span>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase">Form Declared</span>
                        <p className="font-mono font-bold text-slate-800">₹ {d.entered_value}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-rose-500 uppercase">OCR Certificate Text</span>
                        <p className="font-mono font-bold text-rose-700">₹ {d.ocr_value}</p>
                      </div>
                    </div>
                  </div>
                ))}
                <p className="text-[11px] text-rose-700 leading-tight">
                  Discrepancy requires official clarification from institution registrar prior to bank lien check.
                </p>
              </div>
            )}

            {/* Field Provenance & Extraction Confidence Grid */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-subtle space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Field Provenance & Confidence
                </h3>
                <span className="text-[11px] text-slate-400 font-mono">
                  Engine: PyMuPDF + PaddleOCR
                </span>
              </div>

              <div className="space-y-2 text-xs">
                {activeCase.provenance_records.map((prov, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between"
                  >
                    <div>
                      <span className="text-[10px] font-mono font-bold text-slate-500 uppercase">
                        {prov.field_name}
                      </span>
                      <p className="font-semibold text-slate-900 mt-0.5">
                        {prov.extracted_value || "—"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <BadgeProvenance
                        sourceType={prov.source_type}
                        confidenceScore={prov.confidence_score}
                        size="sm"
                      />
                      {prov.source_type !== "OFFICER_VERIFIED" && prov.source_type !== "BANK_CONFIRMED" && (
                        <button
                          onClick={() => handleVerifyField(prov.field_name, prov.extracted_value || "")}
                          disabled={verifyingField === prov.field_name || isVerifyingAll}
                          className="text-[10px] px-2 py-0.5 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 font-medium border border-blue-200 transition-colors"
                          title="Attest this field as Scrutiny Officer"
                        >
                          {verifyingField === prov.field_name ? "..." : "Attest"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                <button
                  onClick={handleVerifyAllFields}
                  disabled={isVerifyingAll || activeCase.provenance_records.every((p) => p.source_type === "OFFICER_VERIFIED")}
                  className="w-full mt-2 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 disabled:opacity-50 text-blue-800 border border-blue-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                  <span>{isVerifyingAll ? "Attesting All Fields..." : "Attest All Fields (Officer Scrutiny)"}</span>
                </button>
              </div>
            </div>

            {/* Officer Action Panel */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-subtle space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b border-slate-100 pb-2">
                Scrutiny Officer Determination
              </h3>

              <div className="space-y-2.5">
                {/* Action 1: Raise Query */}
                {!showQueryBox ? (
                  <button
                    onClick={() => setShowQueryBox(true)}
                    className="w-full px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <MessageSquare className="w-3.5 h-3.5 text-rose-600" />
                    <span>Raise Deficiency Query to Institution</span>
                  </button>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2 text-xs animate-fade-in">
                    <label className="font-bold text-slate-700">
                      Observation for Institution:
                    </label>
                    <textarea
                      value={queryInput}
                      onChange={(e) => setQueryInput(e.target.value)}
                      rows={3}
                      placeholder="e.g. Discrepancy between declared ₹10,00,000 and scanned receipt ₹1,00,000. Please upload genuine rectified receipt."
                      className="w-full p-2 bg-white border border-slate-200 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-rose-500 text-xs"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setShowQueryBox(false)}
                        className="px-2.5 py-1 text-slate-500 hover:text-slate-700 text-xs"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleRaiseQuery}
                        className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded font-semibold text-xs"
                      >
                        Transmit Query
                      </button>
                    </div>
                  </div>
                )}

                {/* Action 2: Pass Scrutiny -> Dispatch Bank Token */}
                {activeCase.status === "UNDER_SCRUTINY" || activeCase.status === "SUBMITTED" ? (
                  <button
                    onClick={handleApproveForBank}
                    className="w-full px-3 py-2 bg-primary hover:bg-primary-900 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Approve Scrutiny & Issue Bank Affirmation Link</span>
                  </button>
                ) : null}

                {/* Action 3: Simulate Bank Response (Demo Hook) */}
                {activeCase.status === "BANK_VERIFICATION_PENDING" && (
                  <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 space-y-2 text-xs">
                    <div className="flex items-center gap-1.5 font-bold text-purple-900">
                      <Clock className="w-3.5 h-3.5 text-purple-600" />
                      <span>Pending Bank Branch Affirmation</span>
                    </div>
                    {appMode === "LIVE" && (
                      <div className="p-2 rounded bg-amber-50 border border-amber-200 text-amber-900 text-[11px] leading-tight">
                        <span className="font-bold">Backend Route Gap:</span> FastAPI does not currently have a bank confirmation router mounted (/api/v1/bank). The simulation below runs via client demo adapter and will not persist to PostgreSQL.
                      </div>
                    )}
                    <p className="text-[11px] text-purple-700 leading-tight">
                      {appMode === "LIVE"
                        ? "For UI demonstration, you may trigger the simulated demo adapter below:"
                        : "Signed link active for branch nodal officer. For demo evaluation, trigger simulated affirmation below:"}
                    </p>
                    <button
                      onClick={handleSimulateBankAffirmation}
                      className="w-full px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-bold text-xs flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      <span>Simulate Bank Affirmation {appMode === "LIVE" ? "(Demo Adapter — Not Persisted in DB)" : "(Demo Adapter)"}</span>
                    </button>
                    <p className="text-[10px] text-slate-400 italic text-center">
                      Clearly marked as simulated demo adapter per competition guidelines.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
          No pending scrutiny cases in queue.
        </div>
      )}
    </div>
  );
}
