"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { formatDate, truncateHash } from "@/lib/utils";
import {
  X,
  ShieldCheck,
  ShieldAlert,
  AlertOctagon,
  RefreshCw,
  CheckCircle2,
  FileCode2,
  Lock,
} from "lucide-react";

interface AuditLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLedgerModal: React.FC<AuditLedgerModalProps> = ({
  isOpen,
  onClose,
}) => {
  const {
    auditLogs,
    tamperAuditLog,
    resetAuditLedger,
    verifyAuditLedger,
  } = useApp();

  const [verifyResult, setVerifyResult] = useState<{
    valid: boolean;
    broken_at_id: number | null;
    total_records: number;
    message: string;
  } | null>(null);

  const [isVerifying, setIsVerifying] = useState(false);

  if (!isOpen) return null;

  const handleVerify = async () => {
    setIsVerifying(true);
    try {
      const res = await verifyAuditLedger();
      setVerifyResult(res);
    } catch (err: any) {
      setVerifyResult({
        valid: false,
        broken_at_id: null,
        total_records: 0,
        message: `Verification Error: ${err.message}`,
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleTamper = () => {
    // Tamper record 3 or 2
    tamperAuditLog(3);
    setVerifyResult(null);
  };

  const handleReset = () => {
    resetAuditLedger();
    setVerifyResult(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-[#0F1C36] text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary-700/50 rounded-lg border border-primary-500/30">
              <Lock className="w-5 h-5 text-amber-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight">
                  Cryptographic Audit Ledger
                </h2>
                <span className="text-[10px] font-mono uppercase bg-amber-400/20 text-amber-300 px-2 py-0.5 rounded border border-amber-400/30">
                  SHA-256 Chained
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Immutable chronological ledger conforming to SIH26265 specifications
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Verification Status Banner */}
        <div className="p-4 bg-slate-50 border-b border-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={handleVerify}
                disabled={isVerifying}
                className="px-3.5 py-1.5 bg-primary text-white hover:bg-primary-900 text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow-sm transition-all"
              >
                {isVerifying ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <ShieldCheck className="w-3.5 h-3.5" />
                )}
                <span>Verify Chain Integrity</span>
              </button>

              <button
                onClick={handleTamper}
                className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors"
                title="Simulate adversarial database tamper to demonstrate real-time fraud detection"
              >
                <AlertOctagon className="w-3.5 h-3.5" />
                <span>Simulate DB Tamper (Demo Test)</span>
              </button>

              <button
                onClick={handleReset}
                className="px-2.5 py-1.5 bg-white hover:bg-slate-100 text-slate-600 border border-slate-200 text-xs font-medium rounded-lg flex items-center gap-1 transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Reset Ledger</span>
              </button>
            </div>

            <div className="text-xs text-slate-500 font-mono">
              Total Blocks: <strong className="text-slate-800">{auditLogs.length}</strong>
            </div>
          </div>

          {verifyResult && (
            <div
              className={`mt-3 p-3 rounded-xl border flex items-start gap-2.5 text-xs animate-fade-in ${
                verifyResult.valid
                  ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                  : "bg-rose-50 border-rose-200 text-rose-900"
              }`}
            >
              {verifyResult.valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-bold">
                  {verifyResult.valid
                    ? "Cryptographic Ledger Verified (Chain Intact)"
                    : "TAMPER DETECTED: Cryptographic Invalidation"}
                </p>
                <p className="mt-0.5 opacity-90">{verifyResult.message}</p>
              </div>
            </div>
          )}
        </div>

        {/* Ledger Table */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="border border-slate-200 rounded-xl overflow-hidden shadow-subtle">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-100/80 text-slate-600 uppercase text-[10px] font-bold tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Block #</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Details & Actor</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 font-mono">Previous Hash</th>
                  <th className="py-2.5 px-3 font-mono">Current Hash (H_n)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-sans">
                {auditLogs.map((log) => {
                  const isTampered = log.current_hash.startsWith("CORRUPTED_");
                  return (
                    <tr
                      key={log.id}
                      className={`hover:bg-slate-50/70 transition-colors ${
                        isTampered ? "bg-rose-50/80 font-semibold" : ""
                      }`}
                    >
                      <td className="py-2.5 px-3 font-mono font-bold text-slate-900">
                        #{log.id}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 text-slate-800 border border-slate-200">
                          {log.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 max-w-xs">
                        <div className="font-medium text-slate-900 truncate">
                          {log.details}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                          Actor: {log.user_id}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 whitespace-nowrap">
                        {formatDate(log.timestamp)}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                        {truncateHash(log.previous_hash, 6)}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">
                        <span
                          className={
                            isTampered
                              ? "text-rose-600 bg-rose-100 px-1 py-0.5 rounded border border-rose-300"
                              : "text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded border border-emerald-200"
                          }
                        >
                          {truncateHash(log.current_hash, 6)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <FileCode2 className="w-4 h-4 text-slate-400" />
            Formula: H_n = SHA256(H_{"{n-1}"} || Action || Payload || Actor || Timestamp)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium rounded-lg text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
