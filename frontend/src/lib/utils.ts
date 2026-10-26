import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number into standard Indian Rupee format (e.g. ₹ 10,00,000)
 */
export function formatINR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "₹ 0.00";
  }
  const parts = Number(amount).toFixed(2).split(".");
  const integerPart = parts[0];
  const decimalPart = parts[1];

  let result = "";
  if (integerPart.length <= 3) {
    result = integerPart;
  } else {
    const lastThree = integerPart.substring(integerPart.length - 3);
    const otherNumbers = integerPart.substring(0, integerPart.length - 3);
    const withCommas = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    result = withCommas + "," + lastThree;
  }

  return `₹ ${result}.${decimalPart}`;
}

/**
 * Compact Indian Lakhs / Crores formatter for metrics cards
 */
export function formatINRCompact(amount: number): string {
  if (amount >= 10000000) {
    return `₹ ${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (amount >= 100000) {
    return `₹ ${(amount / 100000).toFixed(2)} Lakh`;
  }
  return formatINR(amount);
}

/**
 * Format ISO date string to Indian standard DD MMM YYYY
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

/**
 * Truncate long hash strings for clean display (e.g. 0x8a3f...4e1b)
 */
export function truncateHash(hash: string | null | undefined, chars: number = 6): string {
  if (!hash) return "—";
  if (hash.length <= chars * 2 + 2) return hash;
  return `${hash.slice(0, chars)}...${hash.slice(-chars)}`;
}

/**
 * Calculate days remaining until maturity
 */
export function getDaysUntilMaturity(maturityDateStr: string): number {
  const target = new Date(maturityDateStr).getTime();
  const now = new Date().getTime();
  const diffTime = target - now;
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

/**
 * Determine the overall provenance tier and average confidence score for an FDR
 * based on all its field-level provenance records.
 */
export function getOverallProvenance(
  records?: { source_type: string; confidence_score?: number | null }[]
): {
  sourceType: "INSTITUTION_ENTERED" | "OCR_EXTRACTED" | "OFFICER_VERIFIED" | "BANK_CONFIRMED";
  confidenceScore: number | null;
} {
  if (!records || records.length === 0) {
    return { sourceType: "INSTITUTION_ENTERED", confidenceScore: null };
  }
  if (records.some((r) => r.source_type === "BANK_CONFIRMED")) {
    return { sourceType: "BANK_CONFIRMED", confidenceScore: 1.0 };
  }
  if (records.some((r) => r.source_type === "OFFICER_VERIFIED")) {
    return { sourceType: "OFFICER_VERIFIED", confidenceScore: 1.0 };
  }
  const ocrRecords = records.filter((r) => r.source_type === "OCR_EXTRACTED");
  if (ocrRecords.length > 0) {
    const avgScore =
      ocrRecords.reduce((acc, r) => acc + (r.confidence_score || 0), 0) /
      ocrRecords.length;
    return { sourceType: "OCR_EXTRACTED", confidenceScore: avgScore };
  }
  return { sourceType: "INSTITUTION_ENTERED", confidenceScore: null };
}
