/**
 * AICTE FinTrust - API Client Layer
 * Strictly maps to backend contracts documented in ARCHITECTURE_PLAN.md and FastAPI routes.
 * Never silently falls back from failed live API calls to mock data.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = "ApiError";
  }
}

// Backend Schemas
export interface BackendHealthResponse {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  database: string;
  timestamp: string;
}

export interface BackendFDRDraftRequest {
  id?: number | null;
  institution_id: number;
  fdr_number?: string | null;
  bank_name?: string | null;
  ifsc_code?: string | null;
  principal_amount?: number | null;
  interest_rate?: number | null;
  issue_date?: string | null;
  maturity_date?: string | null;
  lien_holder?: string | null;
  document_path?: string | null;
}

export interface BackendProvenanceRecord {
  id: number;
  fdr_id: number;
  field_name: string;
  source_type: "INSTITUTION_ENTERED" | "OCR_EXTRACTED" | "BANK_CONFIRMED" | "OFFICER_VERIFIED";
  confidence_score: number | null;
  extracted_value: string | null;
  updated_at: string;
}

export interface BackendClearanceResponse {
  id: number;
  fdr_id: number;
  cell_name: "PGRC" | "VIGILANCE" | "APPROVAL_BUREAU" | "LEGAL" | "FINANCE";
  status: "PENDING" | "APPROVED" | "REJECTED";
  remarks: string | null;
  officer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackendFDRResponse {
  id: number;
  institution_id: number;
  fdr_number: string | null;
  bank_name: string | null;
  ifsc_code: string | null;
  principal_amount: number | null;
  interest_rate: number | null;
  issue_date: string | null;
  maturity_date: string | null;
  lien_holder: string;
  status: string;
  document_path: string | null;
  document_hash: string | null;
  tamper_indicators?: string | null;
  noc_path?: string | null;
  noc_signature?: string | null;
  created_at: string;
  updated_at: string;
  provenance_records: BackendProvenanceRecord[];
  clearances: BackendClearanceResponse[];
}

export interface BackendFDRSubmitResponse {
  message: string;
  fdr: BackendFDRResponse;
  audit_hash: string;
}

export interface BackendFDRUploadResponse {
  message: string;
  fdr_id: number;
  document_path: string;
  document_hash: string;
  file_size_bytes: number;
}

export interface BackendDocumentUrlResponse {
  fdr_id: number;
  document_path: string;
  presigned_url: string;
  expires_in_seconds: number;
}

export interface BackendReleaseRequestResponse {
  message: string;
  fdr_id: number;
  fdr_status: string;
  clearances: BackendClearanceResponse[];
}

export interface BackendClearanceActionResponse {
  message: string;
  task: BackendClearanceResponse;
  fdr_status: string;
  all_cells_approved: boolean;
}

export interface BackendReleaseApprovalResponse {
  message: string;
  fdr_id: number;
  fdr_status: string;
  noc_reference: string;
  noc_document_path: string;
  digital_signature: string;
  public_key: string;
  authorized_by: string;
  released_at: string;
}

export interface BackendNOCUrlResponse {
  fdr_id: number;
  noc_reference: string;
  noc_path: string;
  presigned_url: string;
  expires_in_seconds: number;
}

// OCR & Forensics Schemas
export interface BackendExtractedFieldItem {
  field_name: string;
  extracted_value: string | null;
  confidence_score: number;
  source_snippet: string | null;
  needs_human_review: boolean;
}

export interface BackendTamperIndicatorItem {
  indicator_code: string;
  description: string;
  severity: string;
  details?: Record<string, any> | null;
}

export interface BackendDiscrepancyFieldComparison {
  field_name: string;
  submitted_value: string | null;
  extracted_value: string | null;
  is_mismatch: boolean;
  severity: string;
  confidence_score: number;
  provenance_tier: string;
  badge_color: string;
  highlight_snippet: string | null;
}

export interface BackendDiscrepancyReportResponse {
  fdr_id: number;
  has_discrepancies: boolean;
  discrepancy_count: number;
  critical_count: number;
  fields: Record<string, BackendDiscrepancyFieldComparison>;
  tamper_indicators: BackendTamperIndicatorItem[];
  duplicate_warning: string | null;
  recommended_action: string;
}

export interface BackendFieldVerificationResponse {
  message: string;
  fdr_id: number;
  field_name: string;
  verified_value: string;
  provenance_source: string;
  audit_hash: string;
}

// Public Verification Schemas
export interface BackendClearanceSummary {
  cell_name: string;
  status: string;
  officer_id: string | null;
  completed_at: string | null;
  remarks: string | null;
}

export interface BackendPublicVerificationResponse {
  fdr_id: number;
  fdr_number: string;
  institution_name: string;
  aicte_permanent_id: string;
  bank_name: string;
  principal_amount: string;
  fdr_status: string;
  is_released: boolean;
  is_signature_valid: boolean;
  signature_algorithm: string;
  ed25519_signature: string | null;
  public_key_hex: string | null;
  noc_document_path: string | null;
  noc_download_url: string | null;
  clearances: BackendClearanceSummary[];
  verification_timestamp: string;
  message: string;
}

// Reminders & Escalations Schemas
export interface BackendReminderAlertResponse {
  id: number;
  fdr_id: number;
  institution_id: number;
  reminder_type: string;
  offset_days: number;
  due_date: string;
  status: string;
  escalation_level: number;
  assigned_officer_id: string | null;
  sent_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  message: string;
}

// Audit Schemas
export interface BackendAuditLogItem {
  id: number;
  previous_hash: string;
  current_hash: string;
  action: string;
  payload_hash: string;
  user_id: string | null;
  timestamp: string;
  details: string | null;
}

export interface BackendAuditTrailResponse {
  total: number;
  skip: number;
  limit: number;
  items: BackendAuditLogItem[];
}

export interface BackendAuditVerifyResponse {
  valid: boolean;
  broken_at_id: number | null;
  total_records: number;
  message: string;
  broken_links: any[];
  verified_at: string;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
      },
    });
  } catch (netErr: any) {
    throw new ApiError(
      0,
      `Network connection failed: Unable to reach FastAPI backend at ${API_BASE_URL}${endpoint}. Ensure server is running. (${netErr.message})`
    );
  }

  if (!response.ok) {
    let errBody: string;
    try {
      errBody = await response.text();
    } catch {
      errBody = response.statusText;
    }
    throw new ApiError(
      response.status,
      `Backend error ${response.status} from ${endpoint}: ${errBody}`,
      errBody
    );
  }

  return response.json();
}

export const api = {
  // Health checks
  checkHealth: async (): Promise<BackendHealthResponse> => {
    return request<BackendHealthResponse>("/api/health");
  },

  checkLiveProbe: async (): Promise<{ status: string }> => {
    return request<{ status: string }>("/api/health/live");
  },

  // FDR Endpoints
  saveDraft: async (
    payload: BackendFDRDraftRequest
  ): Promise<BackendFDRResponse> => {
    return request<BackendFDRResponse>("/api/v1/fdr/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  submitFDR: async (id: number): Promise<BackendFDRSubmitResponse> => {
    return request<BackendFDRSubmitResponse>(`/api/v1/fdr/${id}/submit`, {
      method: "POST",
    });
  },

  getFDR: async (id: number): Promise<BackendFDRResponse> => {
    return request<BackendFDRResponse>(`/api/v1/fdr/${id}`);
  },

  getInstitutionFDRs: async (
    instId: number
  ): Promise<BackendFDRResponse[]> => {
    return request<BackendFDRResponse[]>(`/api/v1/fdr/institution/${instId}`);
  },

  uploadDocument: async (
    id: number,
    file: File | Blob,
    filename = "certificate.pdf"
  ): Promise<BackendFDRUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file, filename);

    return request<BackendFDRUploadResponse>(
      `/api/v1/fdr/${id}/upload-document`,
      {
        method: "POST",
        body: formData,
      }
    );
  },

  getDocumentUrl: async (id: number): Promise<BackendDocumentUrlResponse> => {
    return request<BackendDocumentUrlResponse>(`/api/v1/fdr/${id}/document-url`);
  },

  validateFDROCR: async (
    id: number
  ): Promise<BackendDiscrepancyReportResponse> => {
    return request<BackendDiscrepancyReportResponse>(
      `/api/v1/fdr/${id}/validate-ocr`,
      { method: "POST" }
    );
  },

  // OCR Forensics & Verification Endpoints
  processOCR: async (
    fdrId: number,
    file?: File | Blob
  ): Promise<any> => {
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      return request<any>(`/api/v1/ocr/${fdrId}/process`, {
        method: "POST",
        body: formData,
      });
    }
    return request<any>(`/api/v1/ocr/${fdrId}/process`, { method: "POST" });
  },

  getDiscrepancies: async (
    fdrId: number
  ): Promise<BackendDiscrepancyReportResponse> => {
    return request<BackendDiscrepancyReportResponse>(
      `/api/v1/ocr/${fdrId}/discrepancies`
    );
  },

  verifyField: async (
    fdrId: number,
    fieldName: string,
    acceptedValue: string,
    officerId: string,
    remarks?: string
  ): Promise<BackendFieldVerificationResponse> => {
    return request<BackendFieldVerificationResponse>(
      `/api/v1/ocr/${fdrId}/verify-field`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field_name: fieldName,
          accepted_value: acceptedValue,
          officer_id: officerId,
          remarks: remarks || null,
        }),
      }
    );
  },

  // Clearance Gate Endpoints
  requestRelease: async (
    fdrId: number
  ): Promise<BackendReleaseRequestResponse> => {
    return request<BackendReleaseRequestResponse>(
      `/api/v1/clearance/${fdrId}/request-release`,
      { method: "POST" }
    );
  },

  updateClearanceAction: async (
    taskId: number,
    status: "APPROVED" | "REJECTED",
    remarks?: string | null,
    officerId?: string | null
  ): Promise<BackendClearanceActionResponse> => {
    return request<BackendClearanceActionResponse>(
      `/api/v1/clearance/${taskId}/action`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          remarks: remarks || null,
          officer_id: officerId || "SYSTEM_OFFICER",
        }),
      }
    );
  },

  approveRelease: async (
    fdrId: number,
    officerId = "COMPETENT_AUTHORITY",
    remarks?: string | null
  ): Promise<BackendReleaseApprovalResponse> => {
    const params = new URLSearchParams({ officer_id: officerId });
    if (remarks) params.append("remarks", remarks);

    return request<BackendReleaseApprovalResponse>(
      `/api/v1/clearance/${fdrId}/approve-release?${params.toString()}`,
      { method: "POST" }
    );
  },

  getNOCUrl: async (fdrId: number): Promise<BackendNOCUrlResponse> => {
    return request<BackendNOCUrlResponse>(
      `/api/v1/clearance/${fdrId}/noc-url`
    );
  },

  // Public Verification Endpoint
  verifyPublicRelease: async (
    fdrId: number
  ): Promise<BackendPublicVerificationResponse> => {
    return request<BackendPublicVerificationResponse>(
      `/api/v1/verify/${fdrId}`
    );
  },

  // Reminders & Escalations Endpoints
  getActiveReminders: async (
    role = "ALL",
    institutionId?: number,
    officerId?: string
  ): Promise<BackendReminderAlertResponse[]> => {
    const params = new URLSearchParams({ role });
    if (institutionId) params.append("institution_id", String(institutionId));
    if (officerId) params.append("officer_id", officerId);

    return request<BackendReminderAlertResponse[]>(
      `/api/v1/reminders/active?${params.toString()}`
    );
  },

  acknowledgeReminder: async (
    id: number,
    actorId?: string
  ): Promise<BackendReminderAlertResponse> => {
    return request<BackendReminderAlertResponse>(
      `/api/v1/reminders/${id}/acknowledge`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: actorId || null }),
      }
    );
  },

  // Audit Ledger Endpoints
  getAuditTrail: async (
    skip = 0,
    limit = 50,
    action?: string,
    userId?: string
  ): Promise<BackendAuditTrailResponse> => {
    const params = new URLSearchParams({
      skip: String(skip),
      limit: String(limit),
    });
    if (action) params.append("action", action);
    if (userId) params.append("user_id", userId);

    return request<BackendAuditTrailResponse>(
      `/api/v1/audit/trail?${params.toString()}`
    );
  },

  verifyAuditIntegrity: async (): Promise<BackendAuditVerifyResponse> => {
    return request<BackendAuditVerifyResponse>("/api/v1/audit/verify");
  },
};
