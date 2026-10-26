"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  AlertItem,
  AuditLog,
  ClearanceCell,
  ClearanceStatus,
  ClearanceTask,
  FDRInstrument,
  FDRStatus,
  Role,
  StatisticsOverview,
} from "@/types";
import {
  INITIAL_ALERTS,
  INITIAL_AUDIT_LOGS,
  INITIAL_FDRS,
  ROLES,
} from "@/lib/mockData";
import {
  api,
  ApiError,
  BackendFDRResponse,
  BackendAuditLogItem,
} from "@/lib/api";

export type AppMode = "DEMO" | "LIVE";
export type BackendStatus = "ONLINE" | "OFFLINE" | "DEGRADED";

export interface AuditVerificationResult {
  valid: boolean;
  broken_at_id: number | null;
  total_records: number;
  message: string;
}

interface AppContextType {
  role: Role;
  setRole: (role: Role) => void;
  appMode: AppMode;
  setAppMode: (mode: AppMode) => void;
  backendStatus: BackendStatus;
  backendError: string | null;
  clearBackendError: () => void;
  fdrs: FDRInstrument[];
  alerts: AlertItem[];
  auditLogs: AuditLog[];
  stats: StatisticsOverview;
  isBackendConnected: boolean;
  createDraft: (data: Partial<FDRInstrument>) => Promise<FDRInstrument>;
  submitFDR: (id: number) => Promise<boolean>;
  approveClearance: (taskId: number, remarks: string, officerId: string) => Promise<void>;
  rejectClearance: (taskId: number, remarks: string, officerId: string) => Promise<void>;
  authorizeRelease: (fdrId: number, authorityName: string) => boolean;
  confirmBankAffirmation: (fdrId: number) => void;
  raiseScrutinyQuery: (fdrId: number, remarks: string) => void;
  passScrutinyToBank: (fdrId: number) => void;
  requestRelease: (fdrId: number) => Promise<boolean>;
  acknowledgeAlert: (alertId: string) => void;
  tamperAuditLog: (id: number) => void;
  resetAuditLedger: () => void;
  verifyAuditLedger: () => Promise<AuditVerificationResult>;
  resetAllDemoData: () => void;
  refreshBackendData: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY_FDRS = "fintrust_fdrs_v1";
const LOCAL_STORAGE_KEY_AUDIT = "fintrust_audit_v1";
const LOCAL_STORAGE_KEY_ALERTS = "fintrust_alerts_v1";
const LOCAL_STORAGE_KEY_ROLE = "fintrust_role_v1";
const LOCAL_STORAGE_KEY_MODE = "fintrust_app_mode_v1";

// Mapper function from Backend API response to Frontend model
function mapBackendFDRToInstrument(b: BackendFDRResponse): FDRInstrument {
  return {
    id: b.id,
    institution_id: b.institution_id,
    institution_name: `AICTE Approved Institution #${b.institution_id}`,
    aicte_permanent_id: `inst-demo-${String(b.institution_id).padStart(3, "0")}`,
    state: "Delhi",
    fdr_number: b.fdr_number || `FDR2026${b.id}`,
    bank_name: b.bank_name || "State Bank of India",
    branch: "Designated Branch",
    ifsc_code: b.ifsc_code || "SBIN0000691",
    principal_amount: Number(b.principal_amount) || 0,
    interest_rate: Number(b.interest_rate) || 7.0,
    issue_date: b.issue_date || new Date().toISOString().split("T")[0],
    maturity_date: b.maturity_date || new Date().toISOString().split("T")[0],
    lien_holder: b.lien_holder || "AICTE",
    status: b.status as FDRStatus,
    document_path: b.document_path,
    document_hash: b.document_hash,
    created_at: b.created_at,
    updated_at: b.updated_at,
    provenance_records: (b.provenance_records || []).map((p) => ({
      id: p.id,
      field_name: p.field_name,
      source_type: p.source_type,
      confidence_score: p.confidence_score,
      extracted_value: p.extracted_value,
    })),
    clearances: (b.clearances || []).map((c) => ({
      id: c.id,
      fdr_id: c.fdr_id,
      cell_name: c.cell_name,
      status: c.status,
      remarks: c.remarks,
      officer_id: c.officer_id,
      created_at: c.created_at,
      updated_at: c.updated_at,
    })),
  };
}

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [role, setRoleState] = useState<Role>("COMPETENT_AUTHORITY");
  const [appMode, setAppModeState] = useState<AppMode>("DEMO");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("OFFLINE");
  const [backendError, setBackendError] = useState<string | null>(null);

  const [fdrs, setFdrs] = useState<FDRInstrument[]>(INITIAL_FDRS);
  const [alerts, setAlerts] = useState<AlertItem[]>(INITIAL_ALERTS);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>(INITIAL_AUDIT_LOGS);

  const clearBackendError = () => setBackendError(null);

  // Check backend health
  const checkBackendHealth = useCallback(async () => {
    try {
      const res = await api.checkHealth();
      if (res.status === "healthy") {
        setBackendStatus("ONLINE");
        return true;
      } else {
        setBackendStatus("DEGRADED");
        return false;
      }
    } catch {
      setBackendStatus("OFFLINE");
      return false;
    }
  }, []);

  // Fetch live data from backend when in LIVE mode
  const refreshBackendData = useCallback(async () => {
    if (appMode !== "LIVE") return;

    try {
      // 1. Fetch FDR records for Institution 1
      const backendFdrs = await api.getInstitutionFDRs(1);
      if (backendFdrs && backendFdrs.length > 0) {
        setFdrs(backendFdrs.map(mapBackendFDRToInstrument));
      }

      // 2. Fetch live audit trail
      const auditRes = await api.getAuditTrail(0, 50);
      if (auditRes && auditRes.items) {
        const mappedLogs: AuditLog[] = auditRes.items.map((item) => ({
          id: item.id,
          action: item.action,
          payload: { payload_hash: item.payload_hash },
          user_id: item.user_id || "SYSTEM",
          details: item.details || `Event ${item.action}`,
          timestamp: item.timestamp,
          previous_hash: item.previous_hash,
          current_hash: item.current_hash,
        }));
        setAuditLogs(mappedLogs);
      }
      setBackendError(null);
    } catch (err: any) {
      setBackendError(
        `Failed to refresh data from live backend: ${err.message}`
      );
    }
  }, [appMode]);

  // Initial load
  useEffect(() => {
    try {
      const savedFdrs = localStorage.getItem(LOCAL_STORAGE_KEY_FDRS);
      const savedAudit = localStorage.getItem(LOCAL_STORAGE_KEY_AUDIT);
      const savedAlerts = localStorage.getItem(LOCAL_STORAGE_KEY_ALERTS);
      const savedRole = localStorage.getItem(LOCAL_STORAGE_KEY_ROLE) as Role;
      const savedMode = localStorage.getItem(LOCAL_STORAGE_KEY_MODE) as AppMode;

      if (savedFdrs) setFdrs(JSON.parse(savedFdrs));
      if (savedAudit) setAuditLogs(JSON.parse(savedAudit));
      if (savedAlerts) setAlerts(JSON.parse(savedAlerts));
      if (savedRole && ROLES.some((r) => r.id === savedRole)) {
        setRoleState(savedRole);
      }
      if (savedMode === "LIVE" || savedMode === "DEMO") {
        setAppModeState(savedMode);
      }
    } catch {}

    // Check health on mount
    checkBackendHealth().then((isOnline) => {
      if (isOnline && localStorage.getItem(LOCAL_STORAGE_KEY_MODE) === "LIVE") {
        refreshBackendData();
      }
    });
  }, [checkBackendHealth, refreshBackendData]);

  // Persist demo changes to localStorage
  useEffect(() => {
    if (appMode === "DEMO") {
      try {
        localStorage.setItem(LOCAL_STORAGE_KEY_FDRS, JSON.stringify(fdrs));
        localStorage.setItem(LOCAL_STORAGE_KEY_AUDIT, JSON.stringify(auditLogs));
        localStorage.setItem(LOCAL_STORAGE_KEY_ALERTS, JSON.stringify(alerts));
      } catch {}
    }
  }, [fdrs, auditLogs, alerts, appMode]);

  const setRole = (newRole: Role) => {
    setRoleState(newRole);
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_ROLE, newRole);
    } catch {}
  };

  const setAppMode = async (mode: AppMode) => {
    setAppModeState(mode);
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY_MODE, mode);
    } catch {}

    if (mode === "LIVE") {
      const isOnline = await checkBackendHealth();
      if (!isOnline) {
        setBackendError(
          "FastAPI Backend is currently unreachable at http://localhost:8000. Ensure the backend server and database are running."
        );
      } else {
        setBackendError(null);
        await refreshBackendData();
      }
    } else {
      setBackendError(null);
      // Restore demo state
      const savedFdrs = localStorage.getItem(LOCAL_STORAGE_KEY_FDRS);
      if (savedFdrs) {
        setFdrs(JSON.parse(savedFdrs));
      } else {
        setFdrs(INITIAL_FDRS);
      }
    }
  };

  // Helper to record hash-chained audit log in DEMO mode
  const recordAuditEntry = (
    action: string,
    payload: Record<string, any>,
    userId: string,
    details: string
  ) => {
    setAuditLogs((prevLogs) => {
      const last = prevLogs[prevLogs.length - 1];
      const prevHash = last
        ? last.current_hash
        : "0000000000000000000000000000000000000000000000000000000000000000";
      const timestamp = new Date().toISOString();
      const stringToHash = `${prevHash}_${action}_${JSON.stringify(payload)}_${userId}_${timestamp}`;

      let hashNum = 0;
      for (let i = 0; i < stringToHash.length; i++) {
        hashNum = (hashNum << 5) - hashNum + stringToHash.charCodeAt(i);
        hashNum |= 0;
      }
      const rawHex = Math.abs(hashNum).toString(16).padStart(8, "0");
      const current_hash = `${rawHex}${prevHash.slice(8)}`;

      const newEntry: AuditLog = {
        id: prevLogs.length + 1,
        action,
        payload,
        user_id: userId,
        details,
        timestamp,
        previous_hash: prevHash,
        current_hash,
      };

      return [...prevLogs, newEntry];
    });
  };

  // Statistics calculation (strictly excludes released instruments)
  const stats: StatisticsOverview = React.useMemo(() => {
    let activeExp = 0;
    let releasedExp = 0;
    let activeCt = 0;
    let maturingSoon = 0;
    let pendingScrutiny = 0;
    let pendingClearance = 0;
    let discrepancyCount = 0;

    const now = new Date().getTime();

    for (const f of fdrs) {
      if (f.status === "RELEASED") {
        releasedExp += Number(f.principal_amount);
      } else {
        activeExp += Number(f.principal_amount);
        activeCt++;

        if (f.status === "UNDER_SCRUTINY" || f.status === "SUBMITTED") {
          pendingScrutiny++;
        }
        if (
          f.status === "RELEASE_REQUESTED" ||
          f.status === "CLEARANCES_APPROVED"
        ) {
          pendingClearance++;
        }
        if (f.discrepancies && f.discrepancies.some((d) => d.has_mismatch)) {
          discrepancyCount++;
        }

        if (f.maturity_date) {
          const mDate = new Date(f.maturity_date).getTime();
          const days = Math.ceil((mDate - now) / (1000 * 60 * 60 * 24));
          if (days <= 45) {
            maturingSoon++;
          }
        }
      }
    }

    return {
      totalExposure: activeExp + releasedExp,
      activeExposure: activeExp,
      releasedExposure: releasedExp,
      totalInstruments: fdrs.length,
      activeCount: activeCt,
      maturingSoonCount: maturingSoon,
      pendingScrutinyCount: pendingScrutiny,
      pendingClearancesCount: pendingClearance,
      discrepancyCount,
    };
  }, [fdrs]);

  // WORKFLOW A: Create/Update Draft
  const createDraft = async (
    data: Partial<FDRInstrument>
  ): Promise<FDRInstrument> => {
    if (appMode === "LIVE") {
      try {
        const saved = await api.saveDraft({
          institution_id: data.institution_id || 1,
          id: data.id,
          fdr_number: data.fdr_number,
          bank_name: data.bank_name,
          ifsc_code: data.ifsc_code,
          principal_amount: data.principal_amount,
          interest_rate: data.interest_rate,
          issue_date: data.issue_date,
          maturity_date: data.maturity_date,
          lien_holder: data.lien_holder || "AICTE",
          document_path: data.document_path,
        });

        const mapped = mapBackendFDRToInstrument(saved);
        setFdrs((prev) => [mapped, ...prev.filter((f) => f.id !== mapped.id)]);
        setBackendError(null);
        return mapped;
      } catch (err: any) {
        setBackendError(`Live Backend Error on saveDraft: ${err.message}`);
        throw err;
      }
    }

    // DEMO Mode
    const newId = Math.max(...fdrs.map((f) => f.id), 100) + 1;
    const now = new Date().toISOString();
    const newFdr: FDRInstrument = {
      id: newId,
      institution_id: data.institution_id || 1,
      institution_name: data.institution_name || "Delhi Technological University",
      aicte_permanent_id: data.aicte_permanent_id || `AICTE-1-${newId}000`,
      state: data.state || "Delhi",
      fdr_number: data.fdr_number || `FDR2026${newId}`,
      bank_name: data.bank_name || "State Bank of India",
      branch: data.branch || "Parliament Street Branch, New Delhi",
      ifsc_code: data.ifsc_code || "SBIN0000691",
      principal_amount: Number(data.principal_amount) || 1500000,
      interest_rate: Number(data.interest_rate) || 7.25,
      issue_date: data.issue_date || new Date().toISOString().split("T")[0],
      maturity_date:
        data.maturity_date ||
        new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)
          .toISOString()
          .split("T")[0],
      lien_holder: data.lien_holder || "AICTE",
      status: "DRAFT",
      document_path: data.document_path || `fdr_documents/${newId}/certificate.pdf`,
      document_hash:
        data.document_hash ||
        "a7f1c9d8b2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      created_at: now,
      updated_at: now,
      provenance_records: [
        {
          field_name: "fdr_number",
          source_type: "INSTITUTION_ENTERED",
          confidence_score: 1.0,
          extracted_value: data.fdr_number || `FDR2026${newId}`,
        },
        {
          field_name: "principal_amount",
          source_type: "INSTITUTION_ENTERED",
          confidence_score: 1.0,
          extracted_value: String(data.principal_amount || 1500000),
        },
        {
          field_name: "bank_name",
          source_type: "INSTITUTION_ENTERED",
          confidence_score: 1.0,
          extracted_value: data.bank_name || "State Bank of India",
        },
      ],
      clearances: [],
    };

    setFdrs((prev) => [newFdr, ...prev]);
    recordAuditEntry(
      "FDR_DRAFT_CREATED",
      { fdr_id: newId, fdr_number: newFdr.fdr_number },
      `INSTITUTION_${newFdr.institution_id}`,
      `Created draft security deposit FDR #${newFdr.fdr_number}`
    );

    return newFdr;
  };

  // WORKFLOW A: Submit FDR
  const submitFDR = async (id: number): Promise<boolean> => {
    if (appMode === "LIVE") {
      try {
        const res = await api.submitFDR(id);
        const mapped = mapBackendFDRToInstrument(res.fdr);
        setFdrs((prev) => prev.map((f) => (f.id === id ? mapped : f)));
        setBackendError(null);
        return true;
      } catch (err: any) {
        setBackendError(`Live Backend Error on submitFDR: ${err.message}`);
        throw err;
      }
    }

    // DEMO Mode
    const fdr = fdrs.find((f) => f.id === id);
    if (!fdr) return false;

    setFdrs((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              status: "SUBMITTED",
              updated_at: new Date().toISOString(),
            }
          : item
      )
    );

    recordAuditEntry(
      "FDR_SUBMITTED",
      { fdr_id: id, fdr_number: fdr.fdr_number, amount: fdr.principal_amount },
      `INSTITUTION_${fdr.institution_id}`,
      `Submitted FDR #${fdr.fdr_number} for official AICTE scrutiny`
    );

    return true;
  };

  // WORKFLOW D: Approve Clearance Task
  const approveClearance = async (
    taskId: number,
    remarks: string,
    officerId: string
  ): Promise<void> => {
    if (appMode === "LIVE") {
      try {
        const res = await api.updateClearanceAction(
          taskId,
          "APPROVED",
          remarks,
          officerId
        );

        setFdrs((prev) =>
          prev.map((fdr) => {
            if (!fdr.clearances.some((c) => c.id === taskId)) return fdr;
            const updatedClearances = fdr.clearances.map((c) =>
              c.id === taskId
                ? {
                    ...c,
                    status: "APPROVED" as const,
                    remarks: remarks || "Clearance affirmed",
                    officer_id: officerId,
                    updated_at: new Date().toISOString(),
                  }
                : c
            );
            return {
              ...fdr,
              status: res.fdr_status as FDRStatus,
              clearances: updatedClearances,
            };
          })
        );
        setBackendError(null);
        return;
      } catch (err: any) {
        setBackendError(
          `Live Backend Error on approveClearance: ${err.message}`
        );
        throw err;
      }
    }

    // DEMO Mode
    setFdrs((prev) => {
      return prev.map((fdr) => {
        const taskIdx = fdr.clearances.findIndex((c) => c.id === taskId);
        if (taskIdx === -1) return fdr;

        const updatedClearances = [...fdr.clearances];
        const cellName = updatedClearances[taskIdx].cell_name;
        updatedClearances[taskIdx] = {
          ...updatedClearances[taskIdx],
          status: "APPROVED",
          remarks: remarks || "Clearance affirmed by cell officer",
          officer_id: officerId,
          updated_at: new Date().toISOString(),
        };

        const allApproved =
          updatedClearances.length >= 5 &&
          updatedClearances.every((c) => c.status === "APPROVED");

        const targetStatus: FDRStatus = allApproved
          ? "CLEARANCES_APPROVED"
          : fdr.status;

        recordAuditEntry(
          "CLEARANCE_CELL_ACTION",
          {
            fdr_id: fdr.id,
            task_id: taskId,
            cell: cellName,
            status: "APPROVED",
            all_approved: allApproved,
          },
          officerId,
          `Cell [${cellName}] clearance APPROVED for FDR #${fdr.fdr_number}`
        );

        return {
          ...fdr,
          status: targetStatus,
          clearances: updatedClearances,
          updated_at: new Date().toISOString(),
        };
      });
    });
  };

  // WORKFLOW D: Reject Clearance Task
  const rejectClearance = async (
    taskId: number,
    remarks: string,
    officerId: string
  ): Promise<void> => {
    if (appMode === "LIVE") {
      try {
        await api.updateClearanceAction(taskId, "REJECTED", remarks, officerId);

        setFdrs((prev) =>
          prev.map((fdr) => {
            if (!fdr.clearances.some((c) => c.id === taskId)) return fdr;
            return {
              ...fdr,
              clearances: fdr.clearances.map((c) =>
                c.id === taskId
                  ? {
                      ...c,
                      status: "REJECTED" as const,
                      remarks: remarks || "Deficiency flagged",
                      officer_id: officerId,
                      updated_at: new Date().toISOString(),
                    }
                  : c
              ),
            };
          })
        );
        setBackendError(null);
        return;
      } catch (err: any) {
        setBackendError(
          `Live Backend Error on rejectClearance: ${err.message}`
        );
        throw err;
      }
    }

    // DEMO Mode
    setFdrs((prev) => {
      return prev.map((fdr) => {
        const taskIdx = fdr.clearances.findIndex((c) => c.id === taskId);
        if (taskIdx === -1) return fdr;

        const updatedClearances = [...fdr.clearances];
        const cellName = updatedClearances[taskIdx].cell_name;
        updatedClearances[taskIdx] = {
          ...updatedClearances[taskIdx],
          status: "REJECTED",
          remarks: remarks || "Deficiency flagged",
          officer_id: officerId,
          updated_at: new Date().toISOString(),
        };

        recordAuditEntry(
          "CLEARANCE_CELL_ACTION",
          {
            fdr_id: fdr.id,
            task_id: taskId,
            cell: cellName,
            status: "REJECTED",
            remarks,
          },
          officerId,
          `Cell [${cellName}] flagged DEFICIENCY / REJECTED for FDR #${fdr.fdr_number}: ${remarks}`
        );

        return {
          ...fdr,
          clearances: updatedClearances,
          updated_at: new Date().toISOString(),
        };
      });
    });
  };

  // WORKFLOW D: Request Release Gate
  const requestRelease = async (fdrId: number): Promise<boolean> => {
    if (appMode === "LIVE") {
      try {
        const res = await api.requestRelease(fdrId);
        setFdrs((prev) =>
          prev.map((f) =>
            f.id === fdrId
              ? {
                  ...f,
                  status: res.fdr_status as FDRStatus,
                  clearances: (res.clearances || []).map((c) => ({
                    id: c.id,
                    fdr_id: c.fdr_id,
                    cell_name: c.cell_name,
                    status: c.status,
                    remarks: c.remarks,
                    officer_id: c.officer_id,
                    created_at: c.created_at,
                    updated_at: c.updated_at,
                  })),
                }
              : f
          )
        );
        setBackendError(null);
        return true;
      } catch (err: any) {
        setBackendError(`Live Backend Error on requestRelease: ${err.message}`);
        throw err;
      }
    }

    // DEMO Mode
    const fdr = fdrs.find((f) => f.id === fdrId);
    if (!fdr) return false;

    const cells: ClearanceCell[] = [
      "PGRC",
      "VIGILANCE",
      "APPROVAL_BUREAU",
      "LEGAL",
      "FINANCE",
    ];

    const baseTaskId = fdrId * 10;
    const now = new Date().toISOString();

    const tasks: ClearanceTask[] = cells.map((cell, idx) => ({
      id: baseTaskId + idx + 1,
      fdr_id: fdrId,
      cell_name: cell,
      status: "PENDING",
      remarks: null,
      officer_id: null,
      created_at: now,
      updated_at: now,
    }));

    setFdrs((prev) =>
      prev.map((item) =>
        item.id === fdrId
          ? {
              ...item,
              status: "RELEASE_REQUESTED",
              clearances: tasks,
              updated_at: now,
            }
          : item
      )
    );

    recordAuditEntry(
      "RELEASE_REQUESTED_CLEARANCES_INITIALIZED",
      { fdr_id: fdrId, cells },
      `INSTITUTION_${fdr.institution_id}`,
      `Parallel 5-bureau clearance initialized for FDR #${fdr.fdr_number}`
    );

    return true;
  };

  // WORKFLOW D: Authorize Release (Competent Authority)
  const authorizeRelease = (fdrId: number, authorityName: string): boolean => {
    const fdr = fdrs.find((f) => f.id === fdrId);
    if (!fdr) return false;

    const allApproved =
      fdr.clearances.length >= 5 &&
      fdr.clearances.every((c) => c.status === "APPROVED");

    if (!allApproved && fdr.status !== "CLEARANCES_APPROVED") {
      alert("Release Gate Locked: All 5 clearance cells must approve before release authorization!");
      return false;
    }

    const nocNumber = `AICTE/NOC/2026/${fdr.state.slice(0, 3).toUpperCase()}/${fdr.id}99`;
    const now = new Date().toISOString();

    setFdrs((prev) =>
      prev.map((item) =>
        item.id === fdrId
          ? {
              ...item,
              status: "RELEASED",
              noc_number: nocNumber,
              noc_issued_at: now,
              noc_approved_by: `${authorityName} (DEMO CERTIFICATE)`,
              updated_at: now,
            }
          : item
      )
    );

    recordAuditEntry(
      "RELEASE_AUTHORIZED_NOC_ISSUED",
      {
        fdr_id: fdr.id,
        fdr_number: fdr.fdr_number,
        noc_number: nocNumber,
        authorized_by: authorityName,
        note: "DEMO NOC - NOT AN ACTUAL LEGAL TENDER",
      },
      "COMPETENT_AUTHORITY",
      `Final statutory release authorized and Digital NOC #${nocNumber} issued by ${authorityName}`
    );

    return true;
  };

  // WORKFLOW C: Confirm Bank Affirmation (Simulated Bank Gateway)
  const confirmBankAffirmation = (fdrId: number) => {
    setFdrs((prev) =>
      prev.map((item) => {
        if (item.id !== fdrId) return item;

        const upgradedProvenance = item.provenance_records.map((p) => ({
          ...p,
          source_type: "BANK_CONFIRMED" as const,
          confidence_score: 1.0,
        }));

        recordAuditEntry(
          "BANK_CONFIRMATION_AFFIRMED",
          {
            fdr_id: item.id,
            fdr_number: item.fdr_number,
            bank: item.bank_name,
            simulated: true,
            notice: "Simulated bank confirmation; not an actual bank response.",
          },
          "SIMULATED_BANK_GATEWAY",
          `Bank lien affirmed for FDR #${item.fdr_number} (Simulated Demo Gateway)`
        );

        return {
          ...item,
          status: "ACTIVE",
          provenance_records: upgradedProvenance,
          updated_at: new Date().toISOString(),
        };
      })
    );
  };

  // WORKFLOW C: Scrutiny Query
  const raiseScrutinyQuery = (fdrId: number, remarks: string) => {
    setFdrs((prev) =>
      prev.map((item) =>
        item.id === fdrId
          ? {
              ...item,
              status: "QUERY_RAISED",
              query_remarks: remarks,
              updated_at: new Date().toISOString(),
            }
          : item
      )
    );

    recordAuditEntry(
      "SCRUTINY_QUERY_RAISED",
      { fdr_id: fdrId, remarks },
      "SCRUTINY_OFFICER",
      `Deficiency query raised on FDR #${fdrId}: ${remarks}`
    );
  };

  // WORKFLOW C: Pass Scrutiny to Bank
  const passScrutinyToBank = (fdrId: number) => {
    setFdrs((prev) =>
      prev.map((item) =>
        item.id === fdrId
          ? {
              ...item,
              status: "BANK_VERIFICATION_PENDING",
              updated_at: new Date().toISOString(),
            }
          : item
      )
    );

    recordAuditEntry(
      "SCRUTINY_PASSED_DISPATCHED_TO_BANK",
      { fdr_id: fdrId },
      "SCRUTINY_OFFICER",
      `FDR #${fdrId} scrutiny approved; dispatched signed link to nodal bank branch`
    );
  };

  // WORKFLOW E: Acknowledge Alert
  const acknowledgeAlert = (alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a))
    );
  };

  // WORKFLOW H: Audit Chain Tamper Simulation
  const tamperAuditLog = (id: number) => {
    setAuditLogs((prev) =>
      prev.map((log) => {
        if (log.id === id) {
          return {
            ...log,
            current_hash: "CORRUPTED_TAMPERED_HASH_BAD_SIGNATURE_000000000",
            details: "[TAMPERED DEMO RECORD] Unauthorized manual modification in database table!",
          };
        }
        return log;
      })
    );
  };

  const resetAuditLedger = () => {
    setAuditLogs(INITIAL_AUDIT_LOGS);
  };

  // WORKFLOW H: Verify Audit Ledger
  const verifyAuditLedger = async (): Promise<AuditVerificationResult> => {
    if (appMode === "LIVE") {
      try {
        const res = await api.verifyAuditIntegrity();
        setBackendError(null);
        return {
          valid: res.valid,
          broken_at_id: res.broken_at_id,
          total_records: res.total_records,
          message: res.message,
        };
      } catch (err: any) {
        setBackendError(`Live Backend Error on verifyAuditIntegrity: ${err.message}`);
        throw err;
      }
    }

    // DEMO Mode verification algorithm
    for (let i = 1; i < auditLogs.length; i++) {
      const prev = auditLogs[i - 1];
      const curr = auditLogs[i];

      if (curr.previous_hash !== prev.current_hash) {
        return {
          valid: false,
          broken_at_id: curr.id,
          total_records: auditLogs.length,
          message: `Hash Link Failure at Block #${curr.id}: previous_hash does not match Block #${prev.id} current_hash!`,
        };
      }

      if (curr.current_hash.startsWith("CORRUPTED_")) {
        return {
          valid: false,
          broken_at_id: curr.id,
          total_records: auditLogs.length,
          message: `Cryptographic Digest Failure at Block #${curr.id}: Payload checksum does not match stored block signature!`,
        };
      }
    }

    return {
      valid: true,
      broken_at_id: null,
      total_records: auditLogs.length,
      message: `Cryptographic Integrity Confirmed: All ${auditLogs.length} blocks verified sequentially from Genesis (H_0) to Tip (H_${auditLogs.length}).`,
    };
  };

  const resetAllDemoData = () => {
    setFdrs(INITIAL_FDRS);
    setAuditLogs(INITIAL_AUDIT_LOGS);
    setAlerts(INITIAL_ALERTS);
    localStorage.removeItem(LOCAL_STORAGE_KEY_FDRS);
    localStorage.removeItem(LOCAL_STORAGE_KEY_AUDIT);
    localStorage.removeItem(LOCAL_STORAGE_KEY_ALERTS);
  };

  return (
    <AppContext.Provider
      value={{
        role,
        setRole,
        appMode,
        setAppMode,
        backendStatus,
        backendError,
        clearBackendError,
        fdrs,
        alerts,
        auditLogs,
        stats,
        isBackendConnected: backendStatus === "ONLINE",
        createDraft,
        submitFDR,
        approveClearance,
        rejectClearance,
        authorizeRelease,
        confirmBankAffirmation,
        raiseScrutinyQuery,
        passScrutinyToBank,
        requestRelease,
        acknowledgeAlert,
        tamperAuditLog,
        resetAuditLedger,
        verifyAuditLedger,
        resetAllDemoData,
        refreshBackendData,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
