"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { formatINR, formatDate, truncateHash } from "@/lib/utils";
import { BadgeStatus } from "@/components/ui/BadgeStatus";
import { ClearanceCell, FDRInstrument } from "@/types";
import {
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Lock,
  Unlock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileCheck2,
  QrCode,
  Download,
  Building,
  Clock,
  Send,
  ExternalLink,
} from "lucide-react";

export default function ReleaseGatePage() {
  const {
    fdrs,
    role,
    approveClearance,
    rejectClearance,
    authorizeRelease,
    requestRelease,
  } = useApp();

  // Find release-related cases
  const releaseCases = fdrs.filter(
    (f) =>
      f.status === "RELEASE_REQUESTED" ||
      f.status === "CLEARANCES_APPROVED" ||
      f.status === "RELEASED"
  );

  const [selectedCaseId, setSelectedCaseId] = useState<number>(
    releaseCases[0]?.id || 103
  );

  // Clearance action dialog state
  const [activeCellTask, setActiveCellTask] = useState<{
    id: number;
    cell: ClearanceCell;
    currentStatus: string;
  } | null>(null);
  const [actionRemarks, setActionRemarks] = useState<string>("");
  const [officerName, setOfficerName] = useState<string>("Sh. V. K. Sharma (Director, AICTE)");

  const activeCase =
    fdrs.find((f) => f.id === selectedCaseId) || releaseCases[0] || fdrs[0];

  const cells: { id: ClearanceCell; title: string; desc: string }[] = [
    {
      id: "PGRC",
      title: "Public Grievance Redressal Cell (PGRC)",
      desc: "Student complaints, fee refund orders & ombudsman rulings",
    },
    {
      id: "VIGILANCE",
      title: "Chief Vigilance Office",
      desc: "Institutional corruption inquiries, fake degree probes & administrative sanctions",
    },
    {
      id: "APPROVAL_BUREAU",
      title: "AICTE Approval Bureau",
      desc: "Course intake compliance, progressive closure terms (Handbook Clause 6.46)",
    },
    {
      id: "LEGAL",
      title: "Legal Affairs Cell",
      desc: "Court petitions, stay orders, writ appeals in High Court / Supreme Court",
    },
    {
      id: "FINANCE",
      title: "Finance & Accounts Bureau",
      desc: "Penalty dues reconciliation, processing fee clearance & escrow settlement",
    },
  ];

  // Helper to get task by cell
  const getTaskForCell = (cell: ClearanceCell) => {
    return activeCase?.clearances.find((c) => c.cell_name === cell);
  };

  const allCellsApproved =
    activeCase &&
    activeCase.clearances.length >= 5 &&
    activeCase.clearances.every((c) => c.status === "APPROVED");

  const isReleased = activeCase?.status === "RELEASED";

  const handleCellApprove = async (taskId: number) => {
    try {
      await approveClearance(taskId, actionRemarks || "Clearance affirmed without objection", "OFFICER_CELL_DESK");
      setActiveCellTask(null);
      setActionRemarks("");
    } catch (err: any) {
      alert(`Clearance approval failed: ${err.message}`);
    }
  };

  const handleCellReject = async (taskId: number) => {
    if (!actionRemarks) {
      alert("Please provide specific deficiency remarks for rejection.");
      return;
    }
    try {
      await rejectClearance(taskId, actionRemarks, "OFFICER_CELL_DESK");
      setActiveCellTask(null);
      setActionRemarks("");
    } catch (err: any) {
      alert(`Clearance rejection failed: ${err.message}`);
    }
  };

  const handleFinalAuthorize = () => {
    if (!allCellsApproved) {
      alert("Release Gate Locked: All 5 parallel clearances must be in APPROVED state!");
      return;
    }
    const success = authorizeRelease(activeCase.id, officerName);
    if (success) {
      alert(
        `SUCCESS: Release Authorized by ${officerName}! Digital NOC with cryptographic QR hash has been generated.`
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
              Parallel Multi-Bureau Clearance & Release Gate
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800 font-bold border border-blue-200">
              Clearance Engine
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Strict release gating: PGRC, Vigilance, Approval Bureau, Legal & Finance clearance required before release
          </p>
        </div>
      </div>

      {/* Case Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-slate-200">
        {releaseCases.map((item) => {
          const isSelected = item.id === activeCase?.id;
          const pendingCount = item.clearances.filter((c) => c.status === "PENDING").length;

          return (
            <button
              key={item.id}
              onClick={() => {
                setSelectedCaseId(item.id);
                setActiveCellTask(null);
              }}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-t-lg text-xs font-semibold whitespace-nowrap transition-colors border-t border-l border-r ${
                isSelected
                  ? "bg-white border-slate-300 text-primary shadow-subtle -mb-px"
                  : "bg-slate-100/70 border-transparent text-slate-600 hover:bg-slate-100"
              }`}
            >
              <KeyRound className="w-3.5 h-3.5" />
              <span>{item.fdr_number}</span>
              <span className="text-[10px] text-slate-400 font-normal">
                ({item.institution_name.split(" ")[0]})
              </span>
              {item.status === "RELEASED" ? (
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-200 text-slate-700 font-bold">
                  RELEASED
                </span>
              ) : pendingCount > 0 ? (
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-bold">
                  {pendingCount} Pending
                </span>
              ) : (
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800 font-bold">
                  Ready
                </span>
              )}
            </button>
          );
        })}
      </div>

      {activeCase ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column (8 cols): 5-Bureau Clearance Matrix */}
          <div className="lg:col-span-8 space-y-5">
            {/* Institution Case Summary */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    {activeCase.institution_name}
                  </h3>
                  <BadgeStatus status={activeCase.status} size="sm" />
                </div>
                <p className="text-xs text-slate-500">
                  FDR #{activeCase.fdr_number} · {activeCase.bank_name} · Principal:{" "}
                  <strong className="text-slate-800 font-mono">
                    {formatINR(activeCase.principal_amount)}
                  </strong>
                </p>
              </div>

              <div className="text-right">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">
                  Statutory Rule Reference
                </span>
                <span className="text-xs font-semibold text-primary">
                  Handbook Clause 6.46 (2024-27)
                </span>
              </div>
            </div>

            {/* 5-Cell Interactive Matrix */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-subtle overflow-hidden">
              <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Five-Bureau Parallel Clearance Matrix
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    All 5 cells operate independently from their respective queues
                  </p>
                </div>
                <div className="text-xs font-semibold">
                  Approved:{" "}
                  <strong className="text-emerald-700 font-mono">
                    {activeCase.clearances.filter((c) => c.status === "APPROVED").length} / 5
                  </strong>
                </div>
              </div>

              <div className="divide-y divide-slate-100">
                {cells.map((cell) => {
                  const task = getTaskForCell(cell.id);
                  const isApproved = task?.status === "APPROVED";
                  const isRejected = task?.status === "REJECTED";
                  const isPending = !task || task.status === "PENDING";

                  return (
                    <div
                      key={cell.id}
                      className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/60 transition-colors"
                    >
                      <div className="space-y-1 max-w-md">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-slate-900">
                            {cell.title}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              isApproved
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : isRejected
                                ? "bg-rose-50 text-rose-800 border-rose-200"
                                : "bg-amber-50 text-amber-800 border-amber-200"
                            }`}
                          >
                            {isApproved ? "APPROVED" : isRejected ? "DEFICIENCY" : "PENDING"}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500">{cell.desc}</p>
                        {task?.remarks && (
                          <p className="text-xs text-slate-700 italic bg-slate-50 p-1.5 rounded border border-slate-200">
                            &quot;{task.remarks}&quot;
                            <span className="text-[10px] text-slate-400 not-italic block mt-0.5 font-mono">
                              Affirmed by {task.officer_id || "Desk Officer"} on {formatDate(task.updated_at)}
                            </span>
                          </p>
                        )}
                      </div>

                      {/* Action buttons per cell (Active if not released) */}
                      {!isReleased && (
                        <div className="flex items-center gap-2 shrink-0">
                          {task && isPending && (
                            <button
                              onClick={() =>
                                setActiveCellTask({
                                  id: task.id,
                                  cell: cell.id,
                                  currentStatus: task.status,
                                })
                              }
                              className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg text-xs font-semibold transition-colors"
                            >
                              Action Cell Desk
                            </button>
                          )}
                          {isApproved && (
                            <div className="flex items-center gap-1 text-emerald-700 font-semibold text-xs">
                              <CheckCircle2 className="w-4 h-4" />
                              <span>Affirmed</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Cell Action Modal / Inline Box */}
            {activeCellTask && (
              <div className="p-4 bg-slate-50 border border-slate-300 rounded-xl space-y-3 animate-fade-in text-xs">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-800">
                    Execute Clearance: [{activeCellTask.cell}]
                  </h4>
                  <button
                    onClick={() => setActiveCellTask(null)}
                    className="text-slate-400 hover:text-slate-600 font-bold"
                  >
                    Cancel
                  </button>
                </div>
                <label className="block text-slate-600">
                  Officer Remarks / Basis for Decision:
                </label>
                <textarea
                  value={actionRemarks}
                  onChange={(e) => setActionRemarks(e.target.value)}
                  rows={2}
                  placeholder="e.g. All institutional verification terms verified. No objection to deposit release."
                  className="w-full p-2 bg-white border border-slate-200 rounded text-slate-900 focus:outline-none focus:ring-1 focus:ring-primary text-xs"
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => handleCellReject(activeCellTask.id)}
                    className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded font-semibold"
                  >
                    Flag Deficiency (Reject)
                  </button>
                  <button
                    onClick={() => handleCellApprove(activeCellTask.id)}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold"
                  >
                    Affirm Clearance (Approve)
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Column (4 cols): Competent Authority Release Authorization Lock */}
          <div className="lg:col-span-4 space-y-5">
            {/* Authorization Lock Card */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-subtle space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Statutory Release Authorization Lock
                </h3>
                {allCellsApproved ? (
                  <Unlock className="w-4 h-4 text-emerald-600" />
                ) : (
                  <Lock className="w-4 h-4 text-slate-400" />
                )}
              </div>

              {/* Status explanation */}
              {isReleased ? (
                <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 space-y-2 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-900">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>NOC Formally Issued & Released</span>
                  </div>
                  <p className="text-emerald-800 leading-tight">
                    Deposit has been returned to institution. Held lien is revoked and excluded from currently held active exposure.
                  </p>
                  <div className="font-mono text-[11px] text-slate-700 bg-white p-2 rounded border border-emerald-200">
                    <span className="text-slate-400 block text-[9px]">NOC CERTIFICATE:</span>
                    <strong>{activeCase.noc_number}</strong>
                  </div>
                  <Link
                    href={`/verify?ref=${activeCase.fdr_number}`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:underline pt-1"
                  >
                    <span>Inspect Public Verification Page</span>
                    <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
              ) : allCellsApproved ? (
                <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 space-y-3 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-900">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Gate Readiness Confirmed (5/5 Passed)</span>
                  </div>
                  <p className="text-emerald-800 text-[11px] leading-tight">
                    PGRC, Vigilance, Approval Bureau, Legal & Finance clearances verified. The Competent Authority can now execute final release authorization.
                  </p>

                  <div className="space-y-1">
                    <label className="text-[10px] uppercase font-bold text-slate-500">
                      Authorizing Official:
                    </label>
                    <input
                      type="text"
                      value={officerName}
                      onChange={(e) => setOfficerName(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded text-slate-900 text-xs font-medium"
                    />
                  </div>

                  <button
                    onClick={handleFinalAuthorize}
                    className="w-full px-4 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg font-bold text-xs flex items-center justify-center gap-1.5 shadow-md transition-all"
                  >
                    <KeyRound className="w-4 h-4" />
                    <span>Authorize Release & Issue Digital NOC</span>
                  </button>
                </div>
              ) : (
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 space-y-2 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-amber-900">
                    <Lock className="w-4 h-4 text-amber-700" />
                    <span>Authorization Button Locked</span>
                  </div>
                  <p className="text-amber-800 text-[11px] leading-tight">
                    Per the AICTE PS specification, the system never auto-releases. The release button stays strictly disabled until all configured clearances pass.
                  </p>
                  <p className="text-[10px] text-slate-500 italic">
                    Waiting on: Vigilance Cell Affirmation
                  </p>
                </div>
              )}
            </div>

            {/* Digital NOC & QR Preview */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-subtle space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 border-b border-slate-100 pb-2 flex items-center gap-1.5">
                <QrCode className="w-4 h-4 text-primary" />
                <span>Statutory QR NOC Preview</span>
              </h3>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 flex items-center gap-4">
                <div className="w-20 h-20 bg-white rounded-lg border border-slate-300 p-1 flex items-center justify-center shrink-0">
                  {/* Stylized QR representation */}
                  <div className="w-full h-full bg-slate-900 rounded p-1 flex flex-col justify-between">
                    <div className="flex justify-between">
                      <div className="w-4 h-4 bg-white" />
                      <div className="w-4 h-4 bg-white" />
                    </div>
                    <div className="flex justify-center">
                      <div className="w-3 h-3 bg-white" />
                    </div>
                    <div className="flex justify-between">
                      <div className="w-4 h-4 bg-white" />
                      <div className="w-2 h-2 bg-white" />
                    </div>
                  </div>
                </div>

                <div className="text-xs space-y-1">
                  <span className="font-bold text-slate-800 block">
                    No Objection Certificate
                  </span>
                  <p className="text-[10px] text-slate-500 leading-tight">
                    Scannable Ed25519 cryptographic token verified live at /verify/[id]
                  </p>
                  <span className="inline-block text-[10px] font-mono text-primary font-semibold">
                    {activeCase.noc_number || "AICTE/NOC/PENDING"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
          No release requests in current queue.
        </div>
      )}
    </div>
  );
}
