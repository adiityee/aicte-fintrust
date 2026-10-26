export type Role =
  | "INSTITUTION_ADMIN"
  | "SCRUTINY_OFFICER"
  | "CLEARANCE_OFFICER"
  | "COMPETENT_AUTHORITY";

export interface RoleConfig {
  id: Role;
  title: string;
  shortName: string;
  badge: string;
  description: string;
  cell?: ClearanceCell;
}

export type FDRStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "UNDER_SCRUTINY"
  | "QUERY_RAISED"
  | "BANK_VERIFICATION_PENDING"
  | "BANK_VERIFIED"
  | "ACTIVE"
  | "MATURED"
  | "RENEWED"
  | "RELEASE_REQUESTED"
  | "CLEARANCES_APPROVED"
  | "RELEASED"
  | "ENCASHMENT_NOTICE_DRAFTED";

export type ProvenanceSourceType =
  | "INSTITUTION_ENTERED"
  | "OCR_EXTRACTED"
  | "BANK_CONFIRMED";

export interface ProvenanceRecord {
  id?: number;
  field_name: string;
  source_type: ProvenanceSourceType;
  confidence_score: number | null;
  extracted_value: string | null;
}

export type ClearanceCell =
  | "PGRC"
  | "VIGILANCE"
  | "APPROVAL_BUREAU"
  | "LEGAL"
  | "FINANCE";

export type ClearanceStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface ClearanceTask {
  id: number;
  fdr_id: number;
  cell_name: ClearanceCell;
  status: ClearanceStatus;
  remarks?: string | null;
  officer_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ForensicsMetadata {
  is_valid_pdf: boolean;
  eof_count: number;
  incremental_revisions: number;
  creation_date: string | null;
  modified_date: string | null;
  creation_modified_match: boolean | null;
  flags: string[];
}

export interface DiscrepancyField {
  field_name: string;
  label: string;
  entered_value: string;
  ocr_value: string;
  confidence: number;
  has_mismatch: boolean;
  severity: "LOW" | "MEDIUM" | "HIGH";
}

export interface FDRInstrument {
  id: number;
  institution_id: number;
  institution_name: string;
  aicte_permanent_id: string;
  state: string;
  fdr_number: string;
  bank_name: string;
  branch?: string;
  ifsc_code: string;
  principal_amount: number;
  interest_rate: number;
  issue_date: string;
  maturity_date: string;
  lien_holder: string;
  status: FDRStatus;
  document_path?: string | null;
  document_hash?: string | null;
  created_at: string;
  updated_at: string;
  provenance_records: ProvenanceRecord[];
  clearances: ClearanceTask[];
  forensics?: ForensicsMetadata;
  discrepancies?: DiscrepancyField[];
  query_remarks?: string | null;
  noc_number?: string | null;
  noc_issued_at?: string | null;
  noc_approved_by?: string | null;
}

export interface AuditLog {
  id: number;
  action: string;
  payload: Record<string, any>;
  user_id: string;
  details: string;
  timestamp: string;
  previous_hash: string;
  current_hash: string;
}

export interface AlertItem {
  id: string;
  fdr_id: number;
  fdr_number: string;
  institution_name: string;
  title: string;
  description: string;
  action_required: string;
  deadline: string;
  owner: string;
  consequence: string;
  urgency: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  category: "MATURITY" | "SCRUTINY" | "CLEARANCE" | "DISCREPANCY";
  acknowledged: boolean;
  created_at: string;
}

export interface StatisticsOverview {
  totalExposure: number;
  activeExposure: number;
  releasedExposure: number;
  totalInstruments: number;
  activeCount: number;
  maturingSoonCount: number;
  pendingScrutinyCount: number;
  pendingClearancesCount: number;
  discrepancyCount: number;
}
