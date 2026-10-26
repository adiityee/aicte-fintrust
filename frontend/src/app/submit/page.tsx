"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/context/AppContext";
import { formatINR } from "@/lib/utils";
import {
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Save,
  Send,
  Building2,
  Landmark,
  ShieldCheck,
  FileCheck,
  Eye,
  Info,
} from "lucide-react";

export default function InstitutionSubmissionPage() {
  const router = useRouter();
  const { createDraft, submitFDR } = useApp();

  const [step, setStep] = useState<number>(1);
  const [createdFdrId, setCreatedFdrId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isDraftSaving, setIsDraftSaving] = useState<boolean>(false);

  // Form State
  const [formData, setFormData] = useState({
    institution_id: 1,
    institution_name: "Delhi Technological University",
    aicte_permanent_id: "inst-demo-001",
    state: "Delhi",
    fdr_number: "FDR202600999",
    bank_name: "State Bank of India",
    branch: "Parliament Street Branch, New Delhi",
    ifsc_code: "SBIN0000691",
    principal_amount: 1500000,
    interest_rate: 7.25,
    issue_date: "2026-10-26",
    maturity_date: "2027-10-26",
    lien_holder: "AICTE, New Delhi",
    uploaded_file_name: "synthetic_fdr_sample.pdf",
    has_uploaded: true,
    ocr_simulated: true,
    ocr_amount_extracted: "15,00,000.00",
    ocr_confidence: 0.96,
  });

  // Pre-submission Checklist State
  const [checklist, setChecklist] = useState({
    lienMarked: true,
    tenureValid: true,
    bankAuthorized: true,
    originalScanned: true,
    termsAffirmed: false,
  });

  const handleFieldChange = (field: string, val: any) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleSaveDraft = async () => {
    setIsDraftSaving(true);
    try {
      const saved = await createDraft({
        institution_id: formData.institution_id,
        institution_name: formData.institution_name,
        aicte_permanent_id: formData.aicte_permanent_id,
        state: formData.state,
        fdr_number: formData.fdr_number,
        bank_name: formData.bank_name,
        branch: formData.branch,
        ifsc_code: formData.ifsc_code,
        principal_amount: Number(formData.principal_amount),
        interest_rate: Number(formData.interest_rate),
        issue_date: formData.issue_date,
        maturity_date: formData.maturity_date,
        lien_holder: formData.lien_holder,
        document_path: `fdr_documents/drafts/${formData.uploaded_file_name}`,
      });
      setCreatedFdrId(saved.id);
      alert(`Draft successfully saved! Draft ID #${saved.id} is stored in repository.`);
    } catch (err: any) {
      alert(`Draft save error: ${err.message}`);
    } finally {
      setIsDraftSaving(false);
    }
  };

  const handleFinalSubmit = async () => {
    if (!checklist.termsAffirmed) {
      alert("Please confirm the statutory declaration checkbox before submitting.");
      return;
    }

    setIsSubmitting(true);
    try {
      let targetId = createdFdrId;
      if (!targetId) {
        const saved = await createDraft({
          institution_id: formData.institution_id,
          institution_name: formData.institution_name,
          aicte_permanent_id: formData.aicte_permanent_id,
          state: formData.state,
          fdr_number: formData.fdr_number,
          bank_name: formData.bank_name,
          branch: formData.branch,
          ifsc_code: formData.ifsc_code,
          principal_amount: Number(formData.principal_amount),
          interest_rate: Number(formData.interest_rate),
          issue_date: formData.issue_date,
          maturity_date: formData.maturity_date,
          lien_holder: formData.lien_holder,
          document_path: `fdr_documents/${formData.uploaded_file_name}`,
        });
        targetId = saved.id;
      }

      await submitFDR(targetId);
      setStep(4); // Acknowledgement step
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12 animate-fade-in">
      {/* Top Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          Security Deposit & FDR Electronic Submission
        </h1>
        <p className="text-xs text-slate-500">
          Deposit fixed receipts in favor of AICTE as required under the Approval Process Handbook
        </p>
      </div>

      {/* Multi-step Stepper */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-subtle">
        <div className="grid grid-cols-4 gap-2 text-center text-xs">
          {[
            { num: 1, label: "Institution & Bank" },
            { num: 2, label: "Deposit Terms" },
            { num: 3, label: "Document & OCR" },
            { num: 4, label: "Acknowledgement" },
          ].map((s) => (
            <div
              key={s.num}
              className={`p-2 rounded-lg flex flex-col items-center gap-1 transition-all ${
                step === s.num
                  ? "bg-primary text-white font-semibold shadow-sm"
                  : step > s.num
                  ? "bg-emerald-50 text-emerald-800 font-medium border border-emerald-200"
                  : "bg-slate-50 text-slate-400"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  step === s.num
                    ? "bg-white text-primary"
                    : step > s.num
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-200 text-slate-600"
                }`}
              >
                {step > s.num ? "✓" : s.num}
              </div>
              <span className="text-[11px] truncate max-w-full">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Form Content Area */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-subtle space-y-6">
        {/* STEP 1: Institution & Bank */}
        {step === 1 && (
          <div className="space-y-5 animate-fade-in">
            <div className="border-b border-slate-100 pb-3 flex items-center gap-2 text-primary font-bold text-sm">
              <Building2 className="w-4 h-4" />
              <span>Step 1: Institution Particulars & Issuing Bank</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Institution Name
                </label>
                <input
                  type="text"
                  value={formData.institution_name}
                  onChange={(e) => handleFieldChange("institution_name", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  AICTE Permanent ID
                </label>
                <input
                  type="text"
                  value={formData.aicte_permanent_id}
                  onChange={(e) => handleFieldChange("aicte_permanent_id", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  State / Jurisdiction
                </label>
                <input
                  type="text"
                  value={formData.state}
                  onChange={(e) => handleFieldChange("state", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Lien Holder Entity
                </label>
                <input
                  type="text"
                  value={formData.lien_holder}
                  disabled
                  className="w-full px-3 py-2 bg-slate-100 border border-slate-200 rounded-lg text-slate-600 font-medium"
                />
                <span className="text-[10px] text-slate-400">
                  Fixed statutory lien in favor of All India Council for Technical Education
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100">
              <h4 className="text-xs font-bold text-slate-800 mb-3 flex items-center gap-1.5">
                <Landmark className="w-3.5 h-3.5 text-primary" />
                <span>Nodal Bank Branch Details</span>
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Scheduled Bank Name
                  </label>
                  <select
                    value={formData.bank_name}
                    onChange={(e) => handleFieldChange("bank_name", e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900"
                  >
                    <option value="State Bank of India">State Bank of India</option>
                    <option value="Punjab National Bank">Punjab National Bank</option>
                    <option value="HDFC Bank">HDFC Bank</option>
                    <option value="Bank of Baroda">Bank of Baroda</option>
                    <option value="Canara Bank">Canara Bank</option>
                    <option value="ICICI Bank">ICICI Bank</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Branch Name & City
                  </label>
                  <input
                    type="text"
                    value={formData.branch}
                    onChange={(e) => handleFieldChange("branch", e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Bank IFSC Code
                  </label>
                  <input
                    type="text"
                    value={formData.ifsc_code}
                    onChange={(e) => handleFieldChange("ifsc_code", e.target.value.toUpperCase())}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Financial Details & Maturity */}
        {step === 2 && (
          <div className="space-y-5 animate-fade-in">
            <div className="border-b border-slate-100 pb-3 flex items-center gap-2 text-primary font-bold text-sm">
              <Landmark className="w-4 h-4" />
              <span>Step 2: Deposit Amount, Receipt Number & Validity</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  FDR Certificate Number
                </label>
                <input
                  type="text"
                  value={formData.fdr_number}
                  onChange={(e) => handleFieldChange("fdr_number", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono font-bold"
                  placeholder="e.g. FDR20261099"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Principal Deposit Amount (INR)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold">
                    ₹
                  </span>
                  <input
                    type="number"
                    value={formData.principal_amount}
                    onChange={(e) => handleFieldChange("principal_amount", Number(e.target.value))}
                    className="w-full pl-8 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono font-bold"
                  />
                </div>
                <span className="text-[10px] text-primary font-semibold mt-0.5 block">
                  {formatINR(formData.principal_amount)}
                </span>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Interest Rate (% p.a.)
                </label>
                <input
                  type="number"
                  step="0.05"
                  value={formData.interest_rate}
                  onChange={(e) => handleFieldChange("interest_rate", Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Issue Date
                </label>
                <input
                  type="date"
                  value={formData.issue_date}
                  onChange={(e) => handleFieldChange("issue_date", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Maturity Date
                </label>
                <input
                  type="date"
                  value={formData.maturity_date}
                  onChange={(e) => handleFieldChange("maturity_date", e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900"
                />
                <span className="text-[10px] text-slate-500">
                  Minimum statutory lock-in period applies
                </span>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Supporting Document & OCR Preview */}
        {step === 3 && (
          <div className="space-y-5 animate-fade-in">
            <div className="border-b border-slate-100 pb-3 flex items-center gap-2 text-primary font-bold text-sm">
              <UploadCloud className="w-4 h-4" />
              <span>Step 3: Scanned PDF Certificate & Dual-Pass OCR Verification</span>
            </div>

            {/* Document Upload Box */}
            <div className="p-6 border-2 border-dashed border-slate-300 rounded-xl bg-slate-50/50 hover:bg-slate-50 text-center space-y-3 transition-colors">
              <div className="w-12 h-12 rounded-full bg-primary/10 text-primary mx-auto flex items-center justify-center">
                <FileText className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">
                  {formData.uploaded_file_name} (Attached)
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Uploaded to MinIO encrypted S3 store with server-side AES-256. SHA-256 computed.
                </p>
              </div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Text Layer Extracted via PyMuPDF</span>
              </div>
            </div>

            {/* OCR Live Comparison Preview */}
            <div className="p-4 bg-amber-50/50 rounded-xl border border-amber-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-amber-700" />
                  <span className="text-xs font-bold text-amber-900">
                    Dual-Pass Extraction Confidence Score: 96%
                  </span>
                </div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                  Pre-Submission Review
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-white rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase">
                    Institution Entered
                  </span>
                  <p className="font-mono font-bold text-slate-900 mt-1">
                    {formatINR(formData.principal_amount)}
                  </p>
                  <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                    FDR: {formData.fdr_number}
                  </p>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase">
                    OCR Extracted
                  </span>
                  <p className="font-mono font-bold text-emerald-700 mt-1">
                    ₹ {formData.ocr_amount_extracted}
                  </p>
                  <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                    FDR: {formData.fdr_number}
                  </p>
                </div>
              </div>
              <p className="text-[11px] text-amber-800 leading-tight">
                ✓ No amount mismatch detected between form input and scanned bank receipt.
              </p>
            </div>

            {/* Pre-submission Checklist */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3 text-xs">
              <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                <FileCheck className="w-4 h-4 text-primary" />
                <span>Mandatory Pre-Submission Checklist</span>
              </h4>

              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.lienMarked}
                    onChange={(e) => setChecklist({ ...checklist, lienMarked: e.target.checked })}
                    className="w-4 h-4 text-primary rounded"
                  />
                  <span className="text-slate-700">
                    Lien is formally marked on bank certificate in favor of AICTE (Clause 6.46).
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.tenureValid}
                    onChange={(e) => setChecklist({ ...checklist, tenureValid: e.target.checked })}
                    className="w-4 h-4 text-primary rounded"
                  />
                  <span className="text-slate-700">
                    Deposit maturity date satisfies minimum prescribed regulatory tenure.
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.bankAuthorized}
                    onChange={(e) => setChecklist({ ...checklist, bankAuthorized: e.target.checked })}
                    className="w-4 h-4 text-primary rounded"
                  />
                  <span className="text-slate-700">
                    Certificate is signed by authorized branch manager with official branch seal.
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist.termsAffirmed}
                    onChange={(e) => setChecklist({ ...checklist, termsAffirmed: e.target.checked })}
                    className="w-4 h-4 text-primary rounded"
                  />
                  <span className="text-slate-900 font-semibold">
                    I solemnly declare that all particulars entered are authentic and understand that false submission invites statutory derecognition.
                  </span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Acknowledgement */}
        {step === 4 && (
          <div className="py-8 text-center space-y-4 animate-fade-in">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center shadow-subtle">
              <CheckCircle2 className="w-10 h-10" />
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-slate-900">
                FDR Deposit Submission Successfully Locked
              </h2>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Your deposit receipt has been formally queued for AICTE scrutiny. An immutable SHA-256 audit entry has been recorded in the central ledger.
              </p>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 max-w-sm mx-auto text-left text-xs font-mono space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-400">FDR Number:</span>
                <span className="font-bold text-slate-900">{formData.fdr_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Principal Amount:</span>
                <span className="font-bold text-slate-900">{formatINR(formData.principal_amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Current Status:</span>
                <span className="text-blue-700 font-bold">SUBMITTED (Under Scrutiny)</span>
              </div>
            </div>

            <div className="flex items-center justify-center gap-3 pt-4">
              <button
                onClick={() => router.push("/repository")}
                className="px-4 py-2 bg-primary text-white hover:bg-primary-900 text-xs font-semibold rounded-lg shadow-sm"
              >
                View in Repository
              </button>
              <button
                onClick={() => {
                  setStep(1);
                  setCreatedFdrId(null);
                }}
                className="px-4 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium rounded-lg"
              >
                Submit Another FDR
              </button>
            </div>
          </div>
        )}

        {/* Stepper Navigation Buttons */}
        {step < 4 && (
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <div>
              {step > 1 && (
                <button
                  onClick={() => setStep(step - 1)}
                  className="px-3.5 py-2 bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1.5"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Previous</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleSaveDraft}
                disabled={isDraftSaving}
                className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors"
              >
                <Save className="w-3.5 h-3.5 text-slate-500" />
                <span>{isDraftSaving ? "Saving..." : "Save Draft"}</span>
              </button>

              {step < 3 ? (
                <button
                  onClick={() => setStep(step + 1)}
                  className="px-4 py-2 bg-primary hover:bg-primary-900 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm"
                >
                  <span>Next Step</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  onClick={handleFinalSubmit}
                  disabled={isSubmitting || !checklist.termsAffirmed}
                  className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{isSubmitting ? "Locking & Submitting..." : "Submit to AICTE"}</span>
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
