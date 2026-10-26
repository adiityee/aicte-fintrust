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
  source_type: "INSTITUTION_ENTERED" | "OCR_EXTRACTED" | "BANK_CONFIRMED";
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
