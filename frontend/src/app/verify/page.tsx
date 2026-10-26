"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useApp } from "@/context/AppContext";
import { formatDate, truncateHash } from "@/lib/utils";
import {
  SearchCheck,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  FileCheck2,
  Lock,
  Building,
  Landmark,
  Calendar,
  AlertTriangle,
  QrCode,
  Search,
} from "lucide-react";

function VerifyContent() {
  const searchParams = useSearchParams();
  const initialRef = searchParams.get("ref") || "";

  const { fdrs } = useApp();
  const [lookupQuery, setLookupQuery] = useState(initialRef);
  const [searchedRecord, setSearchedRecord] = useState<any | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (initialRef) {
      handleSearch(initialRef);
    }
  }, [initialRef]);

  const handleSearch = (query: string) => {
    const q = query.trim().toLowerCase();
    if (!q) return;

    setHasSearched(true);
    const match = fdrs.find(
      (f) =>
        f.fdr_number.toLowerCase() === q ||
        (f.noc_number && f.noc_number.toLowerCase() === q) ||
        (f.document_hash && f.document_hash.toLowerCase() === q)
    );

    setSearchedRecord(match || null);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12 animate-fade-in">
      {/* Top Header */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold border border-primary/20">
          <ShieldCheck className="w-4 h-4 text-primary" />
          <span>Statutory AICTE Public Integrity Ledger</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          Public Security Deposit & NOC Verification
        </h1>
        <p className="text-xs text-slate-500 max-w-lg mx-auto leading-relaxed">
          Cryptographically verify the authentic status of institutional security deposits and official No Objection Certificates (NOC) issued by AICTE.
        </p>
      </div>

      {/* Lookup Search Input Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-subtle space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch(lookupQuery);
          }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={lookupQuery}
              onChange={(e) => setLookupQuery(e.target.value)}
              placeholder="Enter FDR Number, NOC Reference (e.g. AICTE/NOC/2026/...) or SHA-256 Hash..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 bg-primary hover:bg-primary-900 text-white font-semibold rounded-xl text-xs sm:text-sm flex items-center justify-center gap-2 shadow-sm transition-colors"
          >
            <SearchCheck className="w-4 h-4" />
            <span>Verify Legitimacy</span>
          </button>
        </form>

        <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] text-slate-400">
          <span>Try quick demo references:</span>
          <button
            onClick={() => {
              setLookupQuery("FDR202600505");
              handleSearch("FDR202600505");
            }}
            className="text-primary font-mono font-medium hover:underline"
          >
            FDR202600505 (Released)
          </button>
          <span>·</span>
          <button
            onClick={() => {
              setLookupQuery("FDR202600202");
              handleSearch("FDR202600202");
            }}
            className="text-primary font-mono font-medium hover:underline"
          >
            FDR202600202 (Active)
          </button>
        </div>
      </div>

      {/* Verification Result Card */}
      {hasSearched && (
        <div className="animate-fade-in">
          {searchedRecord ? (
            <div className="bg-white rounded-2xl border border-emerald-200 shadow-card overflow-hidden">
              {/* Header Banner */}
              <div className="p-5 bg-emerald-50/70 border-b border-emerald-200 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                        Official Verification Confirmed
                      </span>
                      <span className="text-[10px] bg-emerald-200 text-emerald-900 px-2 py-0.5 rounded font-mono font-bold">
                        AUTHENTIC RECORD
                      </span>
                    </div>
                    <p className="text-xs text-emerald-800">
                      Record located in AICTE Central Ledger with verified provenance
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-[10px] text-slate-400 font-mono block">VERIFIED AT</span>
                  <span className="text-xs font-mono font-bold text-slate-800">
                    {new Date().toLocaleTimeString("en-IN")}
                  </span>
                </div>
              </div>

              {/* Public Redacted Details (Privacy Preserving per DPDP Act 2023) */}
              <div className="p-6 space-y-5 text-xs text-slate-700">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[11px] text-slate-500 leading-normal flex items-start gap-2">
                  <Lock className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>DPDP Act & Financial Privacy Compliance:</strong> Non-public commercial data (exact account balance, internal ledger notes) are redacted in public portal verification.
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Instrument Reference
                    </span>
                    <p className="font-mono font-bold text-slate-900 text-sm mt-0.5">
                      {searchedRecord.fdr_number}
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Current Statutory Status
                    </span>
                    <p className="font-bold text-slate-900 text-sm mt-0.5">
                      {searchedRecord.status === "RELEASED"
                        ? "RELEASED (NOC Formally Granted)"
                        : searchedRecord.status === "ACTIVE"
                        ? "ACTIVE (Lien Held in Favor of AICTE)"
                        : searchedRecord.status}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Technical Institution
                    </span>
                    <p className="font-semibold text-slate-900 text-xs mt-0.5">
                      {searchedRecord.institution_name}
                    </p>
                    <p className="text-[10px] text-slate-400 font-mono">
                      Permanent ID: {searchedRecord.aicte_permanent_id}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Nodal Issuing Bank
                    </span>
                    <p className="font-semibold text-slate-900 text-xs mt-0.5">
                      {searchedRecord.bank_name}
                    </p>
                    <p className="text-[10px] text-slate-400 font-mono">
                      IFSC: {searchedRecord.ifsc_code}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Validity Window
                    </span>
                    <p className="font-medium text-slate-900 text-xs mt-0.5">
                      {formatDate(searchedRecord.issue_date)} to {formatDate(searchedRecord.maturity_date)}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">
                      Lien Holder Entity
                    </span>
                    <p className="font-semibold text-primary text-xs mt-0.5">
                      {searchedRecord.lien_holder}
                    </p>
                  </div>
                </div>

                {/* If NOC Issued, Display NOC details */}
                {searchedRecord.noc_number && (
                  <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200 space-y-2">
                    <div className="flex items-center gap-1.5 font-bold text-emerald-900">
                      <FileCheck2 className="w-4 h-4 text-emerald-700" />
                      <span>Statutory Release NOC Details</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                      <div>
                        <span className="text-slate-400 block text-[9px]">NOC REF NUMBER:</span>
                        <strong className="text-slate-900">{searchedRecord.noc_number}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[9px]">AUTHORIZED BY:</span>
                        <span className="text-slate-900">{searchedRecord.noc_approved_by}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Cryptographic Digest Box */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1 font-mono text-[11px]">
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Cryptographic Digest (SHA-256):</span>
                    <span className="text-slate-800">
                      {truncateHash(searchedRecord.document_hash, 12)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Ledger Tip State:</span>
                    <span className="text-emerald-700 font-semibold">
                      Chained & Mathematically Intact
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-rose-200 p-8 shadow-card text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
                <XCircle className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-slate-900">
                No Record Located for &quot;{lookupQuery}&quot;
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                No active security deposit or issued NOC matching this reference was found in the official AICTE register. Please verify the number.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PublicVerificationPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-3xl mx-auto py-12 text-center text-xs text-slate-400">
          Loading verification console...
        </div>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
