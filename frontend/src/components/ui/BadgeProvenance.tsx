import React from "react";
import { ProvenanceSourceType } from "@/types";
import { ShieldCheck, Eye, UserCheck, AlertTriangle } from "lucide-react";

interface BadgeProvenanceProps {
  sourceType: ProvenanceSourceType;
  confidenceScore?: number | null;
  size?: "sm" | "md";
  showLabel?: boolean;
}

export const BadgeProvenance: React.FC<BadgeProvenanceProps> = ({
  sourceType,
  confidenceScore,
  size = "md",
  showLabel = true,
}) => {
  if (sourceType === "BANK_CONFIRMED") {
    return (
      <span
        title="Bank Confirmed: Independently affirmed by Bank Gateway (Simulated demo adapter)"
        className={`inline-flex items-center gap-1 font-medium rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800 ${
          size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs"
        }`}
      >
        <ShieldCheck className={size === "sm" ? "w-3 h-3 text-emerald-600" : "w-3.5 h-3.5 text-emerald-600"} />
        {showLabel && <span>Bank Affirmed (Simulated)</span>}
      </span>
    );
  }

  if (sourceType === "OCR_EXTRACTED") {
    const isHigh = confidenceScore ? confidenceScore >= 0.85 : true;
    return (
      <span
        title={`OCR Extracted: PyMuPDF / PaddleOCR text recognition (Confidence: ${
          confidenceScore ? Math.round(confidenceScore * 100) : "--"
        }%)`}
        className={`inline-flex items-center gap-1 font-medium rounded-full border ${
          isHigh
            ? "border-amber-300 bg-amber-50 text-amber-800"
            : "border-red-300 bg-red-50 text-red-800"
        } ${size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs"}`}
      >
        {isHigh ? (
          <Eye className={size === "sm" ? "w-3 h-3 text-amber-600" : "w-3.5 h-3.5 text-amber-600"} />
        ) : (
          <AlertTriangle className={size === "sm" ? "w-3 h-3 text-red-600" : "w-3.5 h-3.5 text-red-600"} />
        )}
        {showLabel && (
          <span>
            OCR {confidenceScore ? `${Math.round(confidenceScore * 100)}%` : ""}
          </span>
        )}
      </span>
    );
  }

  // INSTITUTION_ENTERED (Self-declared)
  return (
    <span
      title="Self-Declared: Entered manually by institution administrator (Not yet verified)"
      className={`inline-flex items-center gap-1 font-medium rounded-full border border-slate-300 bg-slate-100 text-slate-700 ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs"
      }`}
    >
      <UserCheck className={size === "sm" ? "w-3 h-3 text-slate-500" : "w-3.5 h-3.5 text-slate-500"} />
      {showLabel && <span>Self-Declared</span>}
    </span>
  );
};
